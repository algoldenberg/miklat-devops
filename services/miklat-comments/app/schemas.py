"""Pydantic-модели запросов/ответов miklat-comments."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CommentOut(BaseModel):
    id: int
    miklat_id: int
    username: str
    comment: str
    rating: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class CommentCreate(BaseModel):
    username: Optional[str] = "Anonymous"
    comment: str = Field(..., min_length=1, max_length=2000)
    rating: Optional[int] = Field(default=None, ge=1, le=5)


class CommentUpdate(BaseModel):
    """Частичное обновление админом (модерация: правка/скрытие текста)."""
    username: Optional[str] = None
    comment: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    rating: Optional[int] = Field(default=None, ge=1, le=5)


class RatingSummaryOut(BaseModel):
    miklat_id: int
    comments_count: int
    ratings_count: int
    average_rating: Optional[float] = None


class HealthOut(BaseModel):
    status: str


class ReadyOut(BaseModel):
    status: str
    database: str
