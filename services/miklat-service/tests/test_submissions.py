"""
Функциональные тесты публичной заявки на новое укрытие (miklat_submissions,
SNS-триггер #1a). Тот же принцип, что в tests/test_reports.py: настоящий
Postgres+PostGIS, SNS — monkeypatch app.aws_client.
"""

from fastapi.testclient import TestClient

from app import aws_client
from app.main import app


def test_create_submission_success(monkeypatch):
    published = {}
    monkeypatch.setattr(
        aws_client,
        "publish_submission_notification",
        lambda topic_arn, submission: published.update(topic_arn=topic_arn, submission_id=submission["id"]),
    )

    with TestClient(app) as client:
        response = client.post(
            "/submissions",
            json={
                "name": "Новое укрытие во дворе",
                "address": "Rothschild 1, Tel Aviv",
                "lon": 34.7749,
                "lat": 32.0664,
                "type": "public_shelter",
                "capacity": 20,
                "comment": "Проверил лично, дверь открыта круглосуточно",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["name"] == "Новое укрытие во дворе"
    assert body["miklat_id"] is None
    assert published["submission_id"] == body["id"]


def test_create_submission_requires_coordinates(monkeypatch):
    monkeypatch.setattr(aws_client, "publish_submission_notification", lambda *a, **kw: None)
    with TestClient(app) as client:
        response = client.post("/submissions", json={"name": "Без координат"})
    assert response.status_code == 422


def test_sns_failure_does_not_fail_submission_creation(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("SNS is down")

    monkeypatch.setattr(aws_client, "publish_submission_notification", boom)

    with TestClient(app) as client:
        response = client.post("/submissions", json={"lon": 34.78, "lat": 32.08})

    assert response.status_code == 201  # заявка сохранена, несмотря на сбой SNS
    assert response.json()["status"] == "pending"


def test_new_submission_appears_in_admin_pending_list(monkeypatch):
    monkeypatch.setattr(aws_client, "publish_submission_notification", lambda *a, **kw: None)
    admin_headers = {"X-Admin-Key": "test-admin-key"}

    with TestClient(app) as client:
        created = client.post("/submissions", json={"name": "Для админ-модерации", "lon": 34.79, "lat": 32.09}).json()

        pending = client.get("/admin/submissions?status=pending", headers=admin_headers).json()
        pending_ids = [s["id"] for s in pending]
        assert created["id"] in pending_ids

        approved = client.post(f"/admin/submissions/{created['id']}/approve", headers=admin_headers)
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["miklat_id"] is not None
