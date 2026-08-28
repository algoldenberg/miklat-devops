from typing import Any, Optional

from pydantic import BaseModel, Field


class LonLat(BaseModel):
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)


class RouteRequest(BaseModel):
    """Маршрут по произвольному упорядоченному списку точек."""
    waypoints: list[LonLat] = Field(..., min_length=2)


class MiklatRouteRequest(BaseModel):
    """Маршрут через укрытия по их id, в заданном порядке (без оптимизации порядка)."""
    miklat_ids: list[int] = Field(..., min_length=1)
    start: Optional[LonLat] = None


class LegOut(BaseModel):
    distance_m: float
    duration_s: float


class RouteOut(BaseModel):
    total_distance_m: float
    total_duration_s: float
    legs: list[LegOut]
    geometry: dict[str, Any]  # GeoJSON LineString
    profile: str = "foot"


class MiklatRouteOut(RouteOut):
    miklat_ids: list[int]


class HealthOut(BaseModel):
    status: str


class ReadyOut(BaseModel):
    status: str
    database: str
    osrm: str
