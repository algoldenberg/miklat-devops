from fastapi import APIRouter, HTTPException

from app import crud, osrm_client
from app.config import MAX_WAYPOINTS
from app.schemas import MiklatRouteOut, MiklatRouteRequest, RouteOut, RouteRequest

router = APIRouter(tags=["routes"])


def _build_route(coordinates: list[tuple[float, float]]) -> dict:
    try:
        route = osrm_client.get_route(coordinates)
    except osrm_client.OSRMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    legs = [{"distance_m": leg["distance"], "duration_s": leg["duration"]} for leg in route["legs"]]
    return {
        "total_distance_m": route["distance"],
        "total_duration_s": route["duration"],
        "legs": legs,
        "geometry": route["geometry"],
    }


@router.post("/route", response_model=RouteOut)
def post_route(data: RouteRequest):
    """Маршрут по произвольному упорядоченному списку точек (>= 2)."""
    if len(data.waypoints) > MAX_WAYPOINTS:
        raise HTTPException(status_code=422, detail=f"Too many waypoints (max {MAX_WAYPOINTS})")
    coords = [(p.lon, p.lat) for p in data.waypoints]
    return _build_route(coords)


@router.post("/route-through-miklats", response_model=MiklatRouteOut)
def post_route_through_miklats(data: MiklatRouteRequest):
    """
    Маршрут через несколько укрытий по их id, в заданном порядке
    (без оптимизации порядка — TSP не решаем, это осознанное упрощение).
    """
    if len(data.miklat_ids) + (1 if data.start else 0) < 2:
        raise HTTPException(status_code=422, detail="At least 2 points are required (start + 1 miklat, or 2+ miklats)")
    if len(data.miklat_ids) > MAX_WAYPOINTS:
        raise HTTPException(status_code=422, detail=f"Too many waypoints (max {MAX_WAYPOINTS})")

    coords_by_id = crud.get_miklats_coords(data.miklat_ids)
    coords = [coords_by_id[mid] for mid in data.miklat_ids]
    if data.start:
        coords = [(data.start.lon, data.start.lat)] + coords

    result = _build_route(coords)
    result["miklat_ids"] = data.miklat_ids
    return result
