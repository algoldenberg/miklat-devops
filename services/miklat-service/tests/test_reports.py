"""
Функциональные тесты жалоб (miklat_reports, SNS-триггер #2).

БД — настоящий Postgres+PostGIS (см. README про DATABASE_URL при запуске
pytest), SNS — monkeypatch app.aws_client (в песочнице Claude нет сети до
AWS и нет тестового топика; та же схема, что в miklat-photos/tests/test_photos.py).

Тестовое укрытие id=1 должно уже существовать в тестовой БД (см. README).
"""

from fastapi.testclient import TestClient

from app import aws_client
from app.main import app


def test_create_report_success(monkeypatch):
    published = {}
    monkeypatch.setattr(
        aws_client,
        "publish_report_notification",
        lambda topic_arn, report: published.update(topic_arn=topic_arn, report_id=report["id"]),
    )

    with TestClient(app) as client:
        response = client.post(
            "/miklats/1/reports",
            json={"issue_type": "wrong_address", "comment": "Адрес неверный, укрытие в другом месте", "contact": "test@example.com"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["miklat_id"] == 1
    assert body["issue_type"] == "wrong_address"
    assert body["status"] == "pending"
    assert published["report_id"] == body["id"]


def test_create_report_nonexistent_miklat_returns_404(monkeypatch):
    called = []
    monkeypatch.setattr(aws_client, "publish_report_notification", lambda *a, **kw: called.append(True))

    with TestClient(app) as client:
        response = client.post("/miklats/999999/reports", json={"issue_type": "closed"})

    assert response.status_code == 404
    assert called == []


def test_sns_failure_does_not_fail_report_creation(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("SNS is down")

    monkeypatch.setattr(aws_client, "publish_report_notification", boom)

    with TestClient(app) as client:
        response = client.post("/miklats/1/reports", json={"issue_type": "other", "comment": "тест"})

    assert response.status_code == 201  # жалоба сохранена, несмотря на сбой SNS
    assert response.json()["status"] == "pending"


def test_admin_reports_require_key(monkeypatch):
    monkeypatch.setattr(aws_client, "publish_report_notification", lambda *a, **kw: None)
    with TestClient(app) as client:
        no_key = client.get("/admin/reports")
        wrong_key = client.get("/admin/reports", headers={"X-Admin-Key": "wrong"})
    assert no_key.status_code == 401
    assert wrong_key.status_code == 401


def test_admin_resolve_and_invalid_flow(monkeypatch):
    monkeypatch.setattr(aws_client, "publish_report_notification", lambda *a, **kw: None)
    admin_headers = {"X-Admin-Key": "test-admin-key"}

    with TestClient(app) as client:
        to_resolve = client.post("/miklats/1/reports", json={"issue_type": "closed"}).json()
        to_invalidate = client.post("/miklats/1/reports", json={"issue_type": "other"}).json()

        pending_list = client.get("/admin/reports?status=pending", headers=admin_headers).json()
        pending_ids = [r["id"] for r in pending_list]
        assert to_resolve["id"] in pending_ids
        assert to_invalidate["id"] in pending_ids

        resolved = client.post(f"/admin/reports/{to_resolve['id']}/resolve", headers=admin_headers)
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved"

        invalidated = client.post(f"/admin/reports/{to_invalidate['id']}/invalid", headers=admin_headers)
        assert invalidated.status_code == 200
        assert invalidated.json()["status"] == "invalid"

        pending_after = client.get("/admin/reports?status=pending", headers=admin_headers).json()
        pending_ids_after = [r["id"] for r in pending_after]
        assert to_resolve["id"] not in pending_ids_after
        assert to_invalidate["id"] not in pending_ids_after


def test_resolve_nonexistent_report_returns_404(monkeypatch):
    monkeypatch.setattr(aws_client, "publish_report_notification", lambda *a, **kw: None)
    admin_headers = {"X-Admin-Key": "test-admin-key"}
    with TestClient(app) as client:
        response = client.post("/admin/reports/999999/resolve", headers=admin_headers)
    assert response.status_code == 404
