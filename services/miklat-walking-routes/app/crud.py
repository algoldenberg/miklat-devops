import json

from fastapi import HTTPException, status

from app.database import get_cursor

MIKLATS_ALONG_ROUTE_LIMIT = 50


def get_miklat_coords(miklat_id: int) -> tuple[float, float]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT ST_X(geom::geometry) AS lon, ST_Y(geom::geometry) AS lat FROM miklats WHERE id = %s;",
            [miklat_id],
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Miklat {miklat_id} not found")
    return row["lon"], row["lat"]


def miklats_along_route(geometry: dict, buffer_m: float, limit: int = MIKLATS_ALONG_ROUTE_LIMIT) -> list[dict]:
    """Верифицированные миклаты в буфере buffer_m метров вокруг линии
    маршрута (GeoJSON LineString из OSRM), упорядоченные по положению вдоль
    неё (ST_LineLocatePoint, 0..1 от старта к финишу) — то есть в том
    порядке, в котором их встретит идущий по маршруту человек.

    Тот же geography-стиль запросов, что и в miklat-service/app/crud.py:
    geom хранится как GEOGRAPHY(Point,4326), ST_DWithin — сразу в метрах,
    lon/lat наружу — через ST_X/ST_Y(geom::geometry). ST_LineLocatePoint
    работает только с geometry (не geography), поэтому линия маршрута
    приводится к geometry отдельно для этого вызова.
    """
    query = """
        WITH route AS (
            SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)::geography AS geog
        )
        SELECT
            m.id, m.name, m.address, m.city, m.capacity, m.accessible,
            ST_X(m.geom::geometry) AS lon, ST_Y(m.geom::geometry) AS lat,
            m.type, m.description, m.is_verified,
            ST_Distance(m.geom, route.geog) AS distance_to_route_m,
            ST_LineLocatePoint(route.geog::geometry, m.geom::geometry) AS position_on_route
        FROM miklats m, route
        WHERE m.is_verified = TRUE
          AND ST_DWithin(m.geom, route.geog, %s)
        ORDER BY position_on_route
        LIMIT %s;
    """
    with get_cursor() as cur:
        cur.execute(query, [json.dumps(geometry), buffer_m, limit])
        return cur.fetchall()
