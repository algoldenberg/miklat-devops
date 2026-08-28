"""Admin-модерация фото: список/одобрение/отклонение/удаление под X-Admin-Key."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app import aws_client, crud
from app.auth import require_admin
from app.config import DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT, S3_BUCKET_NAME
from app.schemas import PhotoAdminOut

router = APIRouter(prefix="/admin/photos", tags=["admin"], dependencies=[Depends(require_admin)])


def _with_url(photo: dict) -> dict:
    photo = dict(photo)
    photo["url"] = aws_client.generate_presigned_url(S3_BUCKET_NAME, photo["s3_key"])
    return photo


@router.get("", response_model=list[PhotoAdminOut])
def list_photos(
    status: Optional[str] = Query(default=None, pattern="^(pending|approved|rejected)$"),
    limit: int = Query(default=DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(default=0, ge=0),
):
    photos = crud.list_admin_photos(status, limit=limit, offset=offset)
    return [_with_url(p) for p in photos]


@router.post("/{photo_id}/approve", response_model=PhotoAdminOut)
def approve_photo(photo_id: int):
    photo = crud.set_photo_status(photo_id, "approved")
    return _with_url(photo)


@router.post("/{photo_id}/reject", response_model=PhotoAdminOut)
def reject_photo(photo_id: int):
    photo = crud.set_photo_status(photo_id, "rejected")
    return _with_url(photo)


@router.delete("/{photo_id}", status_code=204)
def delete_photo(photo_id: int):
    crud.delete_photo(photo_id)
