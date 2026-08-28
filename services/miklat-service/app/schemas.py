"""Pydantic-модели запросов/ответов miklat-service."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------- miklats ----------

class MiklatOut(BaseModel):
    id: int
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    capacity: Optional[int] = None
    accessible: bool
    lon: float
    lat: float
    type: str
    description: Optional[str] = None
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class MiklatNearestOut(MiklatOut):
    distance_m: float


class MiklatCreate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    capacity: Optional[int] = None
    accessible: bool = True
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    type: str = "public_shelter"
    description: Optional[str] = None
    is_verified: bool = True


class MiklatUpdate(BaseModel):
    """Частичное обновление — все поля опциональны (PATCH-семантика)."""
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    capacity: Optional[int] = None
    accessible: Optional[bool] = None
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    type: Optional[str] = None
    description: Optional[str] = None
    is_verified: Optional[bool] = None


# ---------- miklat_submissions (admin moderation) ----------

class SubmissionOut(BaseModel):
    id: int
    name: Optional[str] = None
    address: Optional[str] = None
    lon: float
    lat: float
    type: Optional[str] = None
    capacity: Optional[int] = None
    comment: Optional[str] = None
    status: str
    reviewed_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    miklat_id: Optional[int] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None


class SubmissionApprove(BaseModel):
    reviewed_by: Optional[str] = "admin"


class SubmissionReject(BaseModel):
    reviewed_by: Optional[str] = "admin"
    rejection_reason: str = Field(..., min_length=1)


class HealthOut(BaseModel):
    status: str


class ReadyOut(BaseModel):
    status: str
    database: str
