"""
Проверка самого проксирования (метод/путь/query/заголовки/тело долетают до
downstream и обратно) — без реальной сети. Общий httpx.AsyncClient сервиса
(app.state.http_client, создаётся в lifespan) подменяется на клиент с
httpx.ASGITransport, подключённым напрямую к маленькому фейковому FastAPI-
приложению — оно просто эхом возвращает, что получило. ASGITransport
игнорирует host/port из URL и всегда стучится в примонтированное
приложение, поэтому не важно, что SERVICE_URLS в этих тестах — "ненастоящие"
http://miklat-service/ и т.п.: реальная адресация здесь не участвует,
проверяется только код самого прокси в app/proxy.py и app/main.py.
"""

import httpx
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.main import app

echo_app = FastAPI()


@echo_app.api_route("/{full_path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def echo(full_path: str, request: Request):
    body = await request.body()
    return {
        "method": request.method,
        "path": f"/{full_path}",
        "query": dict(request.query_params),
        "x_test_header": request.headers.get("x-test-header"),
        "body": body.decode("utf-8", errors="replace"),
    }


def _install_fake_backend():
    """Подменяет общий http-клиент gateway на клиент, всегда бьющий в echo_app."""
    app.state.http_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=echo_app))


def test_proxy_forwards_method_path_query_headers_body():
    with TestClient(app) as client:
        _install_fake_backend()
        response = client.post(
            "/miklats/1/comments",
            params={"limit": "5"},
            headers={"X-Test-Header": "hello"},
            content=b'{"comment":"test"}',
        )

    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "POST"
    assert body["path"] == "/miklats/1/comments"
    assert body["query"] == {"limit": "5"}
    assert body["x_test_header"] == "hello"
    assert body["body"] == '{"comment":"test"}'


def test_proxy_admin_photos_routes_to_photos_service():
    with TestClient(app) as client:
        _install_fake_backend()
        response = client.get("/admin/photos", headers={"X-Admin-Key": "secret"})

    assert response.status_code == 200
    assert response.json()["path"] == "/admin/photos"


def test_proxy_unmatched_path_returns_404():
    with TestClient(app) as client:
        _install_fake_backend()
        response = client.get("/this/does/not/exist")

    assert response.status_code == 404


def test_proxy_unreachable_upstream_returns_503():
    with TestClient(app) as client:
        # клиент без рабочего transport — любой запрос сразу упадёт как RequestError,
        # имитируя недоступный downstream-сервис
        app.state.http_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ConnectError("boom")))
        )
        response = client.get("/miklats")

    assert response.status_code == 503
