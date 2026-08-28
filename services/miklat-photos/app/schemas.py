"""Pydantic-модели запросов/ответов miklat-photos."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PhotoOut(BaseModel):
    id: int
    miklat_id: int
    status: str
    uploaded_at: datetime
    reviewed_at: Optional[datetime] = None
    # Presigned S3 URL, добавляется в routers (не хранится в БД — только
    # s3_key хранится, URL генерируется на лету с ограниченным сроком жизни).
    url: Optional[str] = None


class PhotoAdminOut(PhotoOut):
    s3_key: str
    uploaded_by_ip: Optional[str] = None


class HealthOut(BaseModel):
    status: str


class ReadyOut(BaseModel):
    status: str
    database: str
    s3: str
