from fastapi import APIRouter, HTTPException, Query

from app import crud, osrm_client
from app.metrics import WALKING_ROUTES_CALCULATED_TOTAL
from app.schemas import RouteOut, RouteRequest

router = APIRouter(tags=["walking-routes"])


def _route_response(coordinates: list[tuple[float, float]]) -> RouteOut:
    try:
        route = osrm_client.get_route(coordinates)
    except osrm_client.OSRMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    WALKING_ROUTES_CALCULATED_TOTAL.inc()
    return RouteOut(distance_m=route["distance"], duration_s=route["duration"], geometry=route["geometry"])


@router.post("/route", response_model=RouteOut)
def post_route(data: RouteRequest):
    """Пеший маршрут между двумя произвольными точками."""
    coords = [(data.from_.lon, data.from_.lat), (data.to.lon, data.to.lat)]
    return _route_response(coords)


@router.get("/route-to-miklat/{miklat_id}", response_model=RouteOut)
def get_route_to_miklat(
    miklat_id: int,
    from_lon: float = Query(..., ge=-180, le=180),
    from_lat: float = Query(..., ge=-90, le=90),
):
    """Пеший маршрут от точки пользователя до конкретного укрытия (основной сценарий приложения)."""
    to_lon, to_lat = crud.get_miklat_coords(miklat_id)
    return _route_response([(from_lon, from_lat), (to_lon, to_lat)])