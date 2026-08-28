"""Публичные эндпоинты: загрузка фото укрытия, список одобренных фото."""

import ipaddress
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status

from app import aws_client, crud
from app.config import (
    ALLOWED_CONTENT_TYPES,
    DEFAULT_LIST_LIMIT,
    MAX_LIST_LIMIT,
    MAX_PHOTO_SIZE_BYTES,
    S3_BUCKET_NAME,
)
from app.schemas import PhotoOut

router = APIRouter(prefix="/miklats/{miklat_id}", tags=["photos"])


def _with_url(photo: dict) -> dict:
    photo = dict(photo)
    photo["url"] = aws_client.generate_presigned_url(S3_BUCKET_NAME, photo["s3_key"])
    return photo


def _client_ip(request: Request) -> Optional[str]:
    """`uploaded_by_ip` — колонка INET, поэтому пишем в неё только то, что
    реально парсится как IP. request.client.host не всегда таковым является:
    например, в тестах (Starlette TestClient) это литерал "testclient" —
    без этой проверки INSERT падал бы с InvalidTextRepresentation."""
    host = request.client.host if request.client else None
    if not host:
        return None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return None
    return host


@router.post("/photos", response_model=PhotoOut, status_code=201)
async def upload_photo(miklat_id: int, request: Request, file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {file.content_type}. "
            f"Allowed: {', '.join(ALLOWED_CONTENT_TYPES)}.",
        )

    content = await file.read()
    if len(content) > MAX_PHOTO_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Photo exceeds the {MAX_PHOTO_SIZE_BYTES} bytes limit.",
        )
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty file")

    extension = ALLOWED_CONTENT_TYPES[file.content_type]
    uploaded_by_ip = _client_ip(request)

    photo = crud.create_photo(
        miklat_id=miklat_id,
        content=content,
        content_type=file.content_type,
        extension=extension,
        uploaded_by_ip=uploaded_by_ip,
    )
    return _with_url(photo)


@router.get("/photos", response_model=list[PhotoOut])
def list_photos(
    miklat_id: int,
    limit: int = Query(default=DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(default=0, ge=0),
):
    photos = crud.list_public_photos(miklat_id, limit=limit, offset=offset)
    return [_with_url(p) for p in photos]
