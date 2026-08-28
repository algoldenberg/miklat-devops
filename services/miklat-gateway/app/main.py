"""
miklat-gateway — единая точка входа. Nginx на EC2 #1 (frontend) проксирует
`/api/*` сюда (без префикса `/api` — он снимается на уровне nginx, см.
корневой README); сам gateway работает с "голыми" путями, идентичными
путям самих backend-сервисов, чтобы им самим не пришлось ничего менять.
"""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.config import SERVICE_URLS, UPSTREAM_TIMEOUT_S
from app.proxy import forward_request
from app.routing import resolve_target

logger = logging.getLogger("miklat-gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_S)
    yield
    await app.state.http_client.aclose()


app = FastAPI(
    title="miklat-gateway",
    description="Единая точка входа /api/* — маршрутизация к остальным сервисам (miklat-devops)",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
def health():
    """Liveness — сам gateway жив, ни к чему не обращаемся."""
    return {"status": "ok"}


@app.get("/ready", tags=["meta"])
async def ready(request: Request):
    """Readiness — реальный пинг /health каждого downstream-сервиса.
    Не блокирующе строго: если один сервис недоступен, остальные всё равно
    проверяются, а итог — просто "какие именно сервисы сейчас недоступны"."""
    client: httpx.AsyncClient = request.app.state.http_client
    statuses: dict[str, str] = {}

    for name, base_url in SERVICE_URLS.items():
        try:
            resp = await client.get(f"{base_url.rstrip('/')}/health", timeout=3.0)
            statuses[name] = "up" if resp.status_code == 200 else "down"
        except httpx.RequestError:
            statuses[name] = "down"

    overall_ok = all(status == "up" for status in statuses.values())
    return {"status": "ok" if overall_ok else "degraded", "services": statuses}


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    include_in_schema=False,
)
async def proxy_all(full_path: str, request: Request):
    target_service = resolve_target(request.method, full_path)
    if target_service is None:
        return JSONResponse(status_code=404, content={"detail": "No route matches this path"})

    target_base_url = SERVICE_URLS[target_service]
    client: httpx.AsyncClient = request.app.state.http_client
    return await forward_request(client, target_base_url, request, full_path)
