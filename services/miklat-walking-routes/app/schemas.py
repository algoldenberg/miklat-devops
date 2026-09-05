from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class LonLat(BaseModel):
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)


class RouteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: LonLat = Field(..., alias="from")
    to: LonLat
    # Насколько далеко (в метрах) от линии маршрута искать миклаты "по пути" —
    # см. миклаты вдоль маршрута ниже. 300 м — расстояние комфортного пешего
    # отклонения, согласовано с пользователем (Фаза 6, miklat-work-plan.md).
    buffer_m: float = Field(default=300.0, gt=0, le=2000)


class MiklatAlongRoute(BaseModel):
    """Миклат, найденный в буфере buffer_m метров вокруг маршрута — то же
    поле-набор, что MiklatOut в miklat-service, плюс дистанция до линии
    маршрута и положение вдоль неё (0 = старт, 1 = финиш)."""

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
    distance_to_route_m: float
    position_on_route: float


class RouteOut(BaseModel):
    distance_m: float
    duration_s: float
    geometry: dict[str, Any]  # GeoJSON LineString
    profile: str = "foot"
    # Заполняется только для POST /route (маршрут между двумя произвольными
    # точками) — для /route-to-miklat/{id} всегда пустой список, см. routes.py.
    miklats: list[MiklatAlongRoute] = Field(default_factory=list)


class HealthOut(BaseModel):
    status: str


class ReadyOut(BaseModel):
    status: str
    database: str
    osrm: str
