"""Публичный эндпоинт: заявка на новое укрытие (форма 'добавить укрытие' на
фронтенде, SNS-триггер #1a). Ничего не создаёт в miklats напрямую — попадает
в очередь модерации miklat_submissions, дальше — admin approve/reject
(app/routers/admin.py)."""

from fastapi import APIRouter, Request

from app import crud
from app.routers.reports import _client_ip
from app.schemas import SubmissionCreate, SubmissionOut

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionOut, status_code=201)
def create_submission(data: SubmissionCreate, request: Request):
    return crud.create_submission(data, submitted_by_ip=_client_ip(request))
