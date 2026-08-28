"""Публичный эндпоинт: жалоба на существующее укрытие (SNS-триггер #2)."""

import ipaddress
from typing import Optional

from fastapi import APIRouter, Request

from app import crud
from app.schemas import ReportCreate, ReportOut

router = APIRouter(prefix="/miklats/{miklat_id}", tags=["reports"])


def _client_ip(request: Request) -> Optional[str]:
    """reporter_ip — колонка INET: пишем только то, что реально парсится
    как IP (см. тот же приём в miklat-photos/app/routers/photos.py —
    request.client.host не всегда им является, например "testclient" в
    Starlette TestClient)."""
    host = request.client.host if request.client else None
    if not host:
        return None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return None
    return host


@router.post("/reports", response_model=ReportOut, status_code=201)
def create_report(miklat_id: int, data: ReportCreate, request: Request):
    return crud.create_report(miklat_id, data, reporter_ip=_client_ip(request))
