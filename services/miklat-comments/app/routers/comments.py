"""Публичные эндпоинты: список/создание комментариев, сводка рейтинга."""

from fastapi import APIRouter, Query

from app import crud
from app.config import DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT
from app.metrics import COMMENTS_POSTED_TOTAL
from app.schemas import CommentCreate, CommentOut, RatingSummaryOut

router = APIRouter(prefix="/miklats/{miklat_id}", tags=["comments"])


@router.get("/comments", response_model=list[CommentOut])
def get_comments(
    miklat_id: int,
    limit: int = Query(default=DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(default=0, ge=0),
):
    return crud.list_comments(miklat_id, limit=limit, offset=offset)


@router.post("/comments", response_model=CommentOut, status_code=201)
def post_comment(miklat_id: int, data: CommentCreate):
    result = crud.create_comment(miklat_id, data)
    COMMENTS_POSTED_TOTAL.inc()
    return result


@router.get("/rating-summary", response_model=RatingSummaryOut)
def get_rating_summary(miklat_id: int):
    return crud.rating_summary(miklat_id)
