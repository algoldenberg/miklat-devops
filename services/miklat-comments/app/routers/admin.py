"""Admin-модерация комментариев: правка/удаление под X-Admin-Key."""

from fastapi import APIRouter, Depends

from app import crud
from app.auth import require_admin
from app.schemas import CommentOut, CommentUpdate

router = APIRouter(prefix="/admin/comments", tags=["admin"], dependencies=[Depends(require_admin)])


@router.patch("/{comment_id}", response_model=CommentOut)
def update_comment(comment_id: int, data: CommentUpdate):
    return crud.update_comment(comment_id, data)


@router.delete("/{comment_id}", status_code=204)
def delete_comment(comment_id: int):
    crud.delete_comment(comment_id)
