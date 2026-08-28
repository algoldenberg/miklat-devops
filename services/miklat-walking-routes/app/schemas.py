from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class LonLat(BaseModel):
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)


class RouteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: LonLat = Field(..., alias="from")
    to: LonLat


class RouteOut(BaseModel):
    distance_m: float
    duration_s: float
    geometry: dict[str, Any]  # GeoJSON LineString
    profile: str = "foot"


class HealthOut(BaseModel):
    status: str


class ReadyOut(BaseModel):
    status: str
    database: str
    osrm: str
