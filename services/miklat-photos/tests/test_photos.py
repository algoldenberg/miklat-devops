"""
Функциональные тесты miklat-photos.

БД — настоящий Postgres+PostGIS (см. README/DATABASE_URL при запуске pytest),
тот же подход, что в miklat-service/miklat-comments: реальные SQL-запросы,
FK-проверки и т.п. стоит гонять по-настоящему, раз БД доступна в песочнице.

AWS (S3/SNS) — единственная граница, которую в песочнице Claude невозможно
дёрнуть по-настоящему (нет сети до AWS и нет тестового бакета/топика), поэтому
`app.aws_client` monkeypatch-ится точно так же, как `osrm_client` в
miklat-routes/miklat-walking-routes. Реальную заливку в S3 и получение письма
от SNS проверит пользователь на своей машине после разовой настройки dev
S3-бакета и SNS-топика (Фаза 1, шаг 9 work-plan).

Тестовые укрытия id=1 и id=2 должны уже существовать в тестовой БД (см.
инструкцию по прогону тестов в README).
"""

import io

from fastapi.testclient import TestClient

from app import aws_client
from app.main import app

JPEG_BYTES = b"\xff\xd8\xff" + b"fake-jpeg-body" * 10  # содержимое не важно, только тип/размер


def _upload_file(name="photo.jpg", content=JPEG_BYTES, content_type="image/jpeg"):
    return {"file": (name, io.BytesIO(content), content_type)}


def test_upload_photo_success(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        aws_client,
        "upload_photo",
        lambda bucket, key, content, content_type: captured.update(
            bucket=bucket, key=key, content=content, content_type=content_type
        ),
    )
    monkeypatch.setattr(aws_client, "generate_presigned_url", lambda bucket, key, **kw: f"https://fake-s3/{key}")
    published = {}
    monkeypatch.setattr(
        aws_client,
        "publish_photo_pending_notification",
        lambda topic_arn, photo: published.update(topic_arn=topic_arn, photo_id=photo["id"]),
    )

    with TestClient(app) as client:
        response = client.post("/miklats/1/photos", files=_upload_file())

    assert response.status_code == 201
    body = response.json()
    assert body["miklat_id"] == 1
    assert body["status"] == "pending"
    assert body["url"] == f"https://fake-s3/{captured['key']}"

    assert captured["bucket"]  # берётся из S3_BUCKET_NAME (окружение теста)
    assert captured["key"].startswith("photos/1/")
    assert captured["key"].endswith(".jpg")
    assert captured["content"] == JPEG_BYTES
    assert captured["content_type"] == "image/jpeg"

    assert published["photo_id"] == body["id"]


def test_upload_rejects_wrong_content_type(monkeypatch):
    called = []
    monkeypatch.setattr(aws_client, "upload_photo", lambda *a, **kw: called.append(True))

    with TestClient(app) as client:
        response = client.post(
            "/miklats/1/photos",
            files={"file": ("evil.txt", io.BytesIO(b"not an image"), "text/plain")},
        )

    assert response.status_code == 415
    assert called == []  # до S3 дело не дошло


def test_upload_rejects_too_large(monkeypatch):
    monkeypatch.setattr("app.routers.photos.MAX_PHOTO_SIZE_BYTES", 10)
    called = []
    monkeypatch.setattr(aws_client, "upload_photo", lambda *a, **kw: called.append(True))

    with TestClient(app) as client:
        response = client.post("/miklats/1/photos", files=_upload_file())

    assert response.status_code == 413
    assert called == []


def test_upload_nonexistent_miklat_returns_404(monkeypatch):
    called = []
    monkeypatch.setattr(aws_client, "upload_photo", lambda *a, **kw: called.append(True))

    with TestClient(app) as client:
        response = client.post("/miklats/999999/photos", files=_upload_file())

    assert response.status_code == 404
    assert called == []  # существование проверяется ДО обращения к S3


def test_sns_failure_does_not_fail_upload(monkeypatch):
    monkeypatch.setattr(aws_client, "upload_photo", lambda *a, **kw: None)
    monkeypatch.setattr(aws_client, "generate_presigned_url", lambda *a, **kw: "https://fake-s3/x")

    def boom(*args, **kwargs):
        raise RuntimeError("SNS is down")

    monkeypatch.setattr(aws_client, "publish_photo_pending_notification", boom)

    with TestClient(app) as client:
        response = client.post("/miklats/1/photos", files=_upload_file())

    assert response.status_code == 201  # аплоуд успешен, несмотря на сбой SNS
    assert response.json()["status"] == "pending"


def _admin_flow(monkeypatch):
    monkeypatch.setattr(aws_client, "upload_photo", lambda *a, **kw: None)
    monkeypatch.setattr(aws_client, "generate_presigned_url", lambda bucket, key, **kw: f"https://fake-s3/{key}")
    monkeypatch.setattr(aws_client, "publish_photo_pending_notification", lambda *a, **kw: None)


def test_admin_endpoints_require_key(monkeypatch):
    _admin_flow(monkeypatch)
    with TestClient(app) as client:
        no_key = client.get("/admin/photos")
        wrong_key = client.get("/admin/photos", headers={"X-Admin-Key": "wrong"})
    assert no_key.status_code == 401
    assert wrong_key.status_code == 401


def test_admin_approve_reject_and_public_visibility(monkeypatch):
    _admin_flow(monkeypatch)
    admin_headers = {"X-Admin-Key": "test-admin-key"}

    with TestClient(app) as client:
        upload_pending = client.post("/miklats/2/photos", files=_upload_file()).json()
        upload_to_reject = client.post("/miklats/2/photos", files=_upload_file(name="b.jpg")).json()

        # ещё не одобрено -> не видно в публичном списке
        public_before = client.get("/miklats/2/photos").json()
        assert upload_pending["id"] not in [p["id"] for p in public_before]

        approved = client.post(f"/admin/photos/{upload_pending['id']}/approve", headers=admin_headers)
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        rejected = client.post(f"/admin/photos/{upload_to_reject['id']}/reject", headers=admin_headers)
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"

        public_after = client.get("/miklats/2/photos").json()
        public_ids = [p["id"] for p in public_after]
        assert upload_pending["id"] in public_ids
        assert upload_to_reject["id"] not in public_ids

        admin_list = client.get("/admin/photos?status=pending", headers=admin_headers)
        assert admin_list.status_code == 200
        assert upload_pending["id"] not in [p["id"] for p in admin_list.json()]


def test_admin_delete_removes_photo_and_calls_s3_delete(monkeypatch):
    _admin_flow(monkeypatch)
    deleted = {}
    monkeypatch.setattr(
        aws_client, "delete_photo", lambda bucket, key: deleted.update(bucket=bucket, key=key)
    )
    admin_headers = {"X-Admin-Key": "test-admin-key"}

    with TestClient(app) as client:
        photo = client.post("/miklats/1/photos", files=_upload_file()).json()

        resp = client.delete(f"/admin/photos/{photo['id']}", headers=admin_headers)
        assert resp.status_code == 204
        assert deleted["key"] == photo["url"].removeprefix("https://fake-s3/")

        again = client.delete(f"/admin/photos/{photo['id']}", headers=admin_headers)
        assert again.status_code == 404
