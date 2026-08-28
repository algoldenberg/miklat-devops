"""Публичные эндпоинты: список укрытий, одно укрытие, поиск ближайших."""

from typing import Optional

from fastapi import APIRouter, Query

from app import crud
from app.config import (
    DEFAULT_LIST_LIMIT,
    DEFAULT_NEAREST_LIMIT,
    MAX_LIST_LIMIT,
    MAX_NEAREST_LIMIT,
)
from app.schemas import MiklatNearestOut, MiklatOut

router = APIRouter(prefix="/miklats", tags=["miklats"])


@router.get("", response_model=list[MiklatOut])
def get_miklats(
    city: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = Query(default=DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(default=0, ge=0),
):
    return crud.list_miklats(city=city, type_=type, limit=limit, offset=offset)


@router.get("/nearest", response_model=list[MiklatNearestOut])
def get_nearest_miklats(
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    limit: int = Query(default=DEFAULT_NEAREST_LIMIT, ge=1, le=MAX_NEAREST_LIMIT),
    max_distance_m: Optional[float] = Query(default=None, gt=0),
):
    return crud.nearest_miklats(lon=lon, lat=lat, limit=limit, max_distance_m=max_distance_m)


@router.get("/{miklat_id}", response_model=MiklatOut)
def get_miklat(miklat_id: int):
    return crud.get_miklat(miklat_id)
