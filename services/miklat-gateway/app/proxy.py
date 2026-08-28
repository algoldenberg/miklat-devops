"""
Пересылка запроса на выбранный downstream-сервис через httpx.AsyncClient.

Тело запроса читается целиком и пересылается как есть (без парсинга) —
это специально сделано так, чтобы multipart-загрузка фото (miklat-photos)
проходила через gateway прозрачно, байт в байт, без пересборки.

httpx.AsyncClient создаётся один на приложение (см. app/main.py lifespan) и
передаётся сюда явным параметром — это и есть та единственная точка, которую
подменяют (monkeypatch/ASGITransport) в тестах, реальная сеть в них не участвует.
"""

import httpx
from fastapi import Request
from fastapi.responses import Response

# Заголовки, которые не имеет смысла пересылать as-is в обе стороны —
# либо специфичны для конкретного TCP-хопа (host, content-length,
# transfer-encoding, connection), либо будут пересчитаны получателем сами.
_HOP_BY_HOP_REQUEST_HEADERS = {"host", "content-length", "transfer-encoding", "connection"}
_HOP_BY_HOP_RESPONSE_HEADERS = {"content-length", "transfer-encoding", "connection"}


def _filtered_request_headers(request: Request) -> dict:
    return {k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP_REQUEST_HEADERS}


async def forward_request(client: httpx.AsyncClient, target_base_url: str, request: Request, downstream_path: str) -> Response:
    body = await request.body()
    url = f"{target_base_url.rstrip('/')}/{downstream_path.lstrip('/')}"

    try:
        upstream_response = await client.request(
            method=request.method,
            url=url,
            params=request.query_params,
            headers=_filtered_request_headers(request),
            content=body,
        )
    except httpx.RequestError as exc:
        return Response(
            content=f'{{"detail":"Upstream service unreachable: {exc}"}}',
            status_code=503,
            media_type="application/json",
        )

    response_headers = {
        k: v for k, v in upstream_response.headers.items() if k.lower() not in _HOP_BY_HOP_RESPONSE_HEADERS
    }
    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )
