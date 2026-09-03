"""
Admin-эндпоинты: CRUD укрытий "напрямую" + модерация заявок
(miklat_submissions). Все под защитой X-Admin-Key (см. app/auth.py).
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app import crud
from app.auth import require_admin
from app.config import DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT
from app.metrics import SUBMISSIONS_APPROVED_TOTAL
from app.schemas import (
    MiklatCreate,
    MiklatOut,
    MiklatUpdate,
    ReportOut,
    SubmissionApprove,
    SubmissionOut,
    SubmissionReject,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ---------- miklats CRUD ----------

@router.post("/miklats", response_model=MiklatOut, status_code=201)
def create_miklat(data: MiklatCreate):
    return crud.create_miklat(data)


@router.patch("/miklats/{miklat_id}", response_model=MiklatOut)
def update_miklat(miklat_id: int, data: MiklatUpdate):
    return crud.update_miklat(miklat_id, data)


@router.delete("/miklats/{miklat_id}", status_code=204)
def delete_miklat(miklat_id: int):
    crud.delete_miklat(miklat_id)


# ---------- submissions moderation ----------

@router.get("/submissions", response_model=list[SubmissionOut])
def list_submissions(
    status: Optional[str] = Query(default="pending"),
    limit: int = Query(default=DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(default=0, ge=0),
):
    return crud.list_submissions(status_filter=status, limit=limit, offset=offset)


@router.post("/submissions/{submission_id}/approve", response_model=SubmissionOut)
def approve_submission(submission_id: int, body: SubmissionApprove = SubmissionApprove()):
    result = crud.approve_submission(submission_id, reviewed_by=body.reviewed_by or "admin")
    # Бизнес-метрика Задания 5 — инкремент только здесь, где заявка реально
    # переходит в approved (crud.approve_submission бросает исключение, если
    # заявка не найдена/уже обработана — до этой строки в таком случае не
    # дойдёт).
    SUBMISSIONS_APPROVED_TOTAL.inc()
    return result


@router.post("/submissions/{submission_id}/reject", response_model=SubmissionOut)
def reject_submission(submission_id: int, body: SubmissionReject):
    return crud.reject_submission(
        submission_id, reviewed_by=body.reviewed_by or "admin", rejection_reason=body.rejection_reason
    )


# ---------- reports moderation ----------

@router.get("/reports", response_model=list[ReportOut])
def list_reports(
    status: Optional[str] = Query(default="pending"),
    limit: int = Query(default=DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(default=0, ge=0),
):
    return crud.list_reports(status_filter=status, limit=limit, offset=offset)


@router.post("/reports/{report_id}/resolve", response_model=ReportOut)
def resolve_report(report_id: int):
    return crud.set_report_status(report_id, "resolved")


@router.post("/reports/{report_id}/invalid", response_model=ReportOut)
def invalidate_report(report_id: int):
    return crud.set_report_status(report_id, "invalid")
