from fastapi import HTTPException, status

from app.database import get_cursor


def get_miklats_coords(miklat_ids: list[int]) -> dict[int, tuple[float, float]]:
    """Возвращает {id: (lon, lat)} для всех запрошенных id. 404, если какого-то нет."""
    if not miklat_ids:
        return {}
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, ST_X(geom::geometry) AS lon, ST_Y(geom::geometry) AS lat
            FROM miklats
            WHERE id = ANY(%s);
            """,
            [miklat_ids],
        )
        rows = cur.fetchall()

    found = {row["id"]: (row["lon"], row["lat"]) for row in rows}
    missing = [mid for mid in miklat_ids if mid not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Miklat(s) not found: {missing}",
        )
    return found
