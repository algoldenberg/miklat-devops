from fastapi import HTTPException, status

from app.database import get_cursor


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
