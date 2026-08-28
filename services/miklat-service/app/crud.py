"""
Все SQL-запросы сервиса — явные, без ORM. geom хранится как
GEOGRAPHY(Point,4326); наружу отдаём lon/lat через ST_X/ST_Y(geom::geometry).
"""

import logging
from typing import Optional

from fastapi import HTTPException, status

from app import aws_client
from app.config import SNS_TOPIC_ARN
from app.database import get_cursor

logger = logging.getLogger("miklat-service.crud")

_MIKLAT_COLUMNS = """
    id, name, address, city, capacity, accessible,
    ST_X(geom::geometry) AS lon, ST_Y(geom::geometry) AS lat,
    type, description, is_verified, created_at, updated_at
"""


# ---------- miklats: чтение (публичное) ----------

def list_miklats(
    city: Optional[str],
    type_: Optional[str],
    limit: int,
    offset: int,
    only_verified: bool = True,
) -> list[dict]:
    conditions = []
    params: list = []

    if only_verified:
        conditions.append("is_verified = TRUE")
    if city:
        conditions.append("city = %s")
        params.append(city)
    if type_:
        conditions.append("type = %s")
        params.append(type_)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT {_MIKLAT_COLUMNS}
        FROM miklats
        {where_clause}
        ORDER BY id
        LIMIT %s OFFSET %s;
    """
    params.extend([limit, offset])

    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def get_miklat(miklat_id: int, only_verified: bool = True) -> dict:
    conditions = ["id = %s"]
    params: list = [miklat_id]
    if only_verified:
        conditions.append("is_verified = TRUE")

    query = f"""
        SELECT {_MIKLAT_COLUMNS}
        FROM miklats
        WHERE {' AND '.join(conditions)};
    """
    with get_cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miklat not found")
    return row


def nearest_miklats(
    lon: float,
    lat: float,
    limit: int,
    max_distance_m: Optional[float],
) -> list[dict]:
    conditions = ["is_verified = TRUE"]
    params: list = []

    distance_filter = ""
    if max_distance_m is not None:
        conditions.append("ST_DWithin(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)")
        params.extend([lon, lat, max_distance_m])

    where_clause = f"WHERE {' AND '.join(conditions)}"
    query = f"""
        SELECT {_MIKLAT_COLUMNS},
               ST_Distance(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) AS distance_m
        FROM miklats
        {where_clause}
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
        LIMIT %s;
    """
    # порядок плейсхолдеров: distance_m(lon,lat) -> [опц. ST_DWithin(lon,lat,dist)] -> ORDER BY(lon,lat) -> limit
    full_params = [lon, lat] + params + [lon, lat, limit]

    with get_cursor() as cur:
        cur.execute(query, full_params)
        return cur.fetchall()


# ---------- miklats: запись (admin) ----------

def create_miklat(data) -> dict:
    query = f"""
        INSERT INTO miklats (name, address, city, capacity, accessible, geom, type, description, is_verified)
        VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s, %s)
        RETURNING {_MIKLAT_COLUMNS};
    """
    params = [
        data.name, data.address, data.city, data.capacity, data.accessible,
        data.lon, data.lat, data.type, data.description, data.is_verified,
    ]
    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        return cur.fetchone()


def update_miklat(miklat_id: int, data) -> dict:
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return get_miklat(miklat_id, only_verified=False)

    set_clauses = []
    params: list = []

    # lon/lat вместе собираются в geom, если задан хотя бы один из них —
    # достанем оба текущих значения и подставим отсутствующее.
    if "lon" in fields or "lat" in fields:
        current = get_miklat(miklat_id, only_verified=False)
        lon = fields.pop("lon", current["lon"])
        lat = fields.pop("lat", current["lat"])
        set_clauses.append("geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography")
        params.extend([lon, lat])

    for column, value in fields.items():
        set_clauses.append(f"{column} = %s")
        params.append(value)

    set_clauses.append("updated_at = now()")
    params.append(miklat_id)

    query = f"""
        UPDATE miklats
        SET {', '.join(set_clauses)}
        WHERE id = %s
        RETURNING {_MIKLAT_COLUMNS};
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miklat not found")
    return row


def delete_miklat(miklat_id: int) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM miklats WHERE id = %s RETURNING id;", [miklat_id])
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miklat not found")


# ---------- miklat_submissions: модерация (admin) ----------

_SUBMISSION_COLUMNS = """
    id, name, address,
    ST_X(geom::geometry) AS lon, ST_Y(geom::geometry) AS lat,
    type, capacity, comment, status, reviewed_by, rejection_reason,
    miklat_id, submitted_at, reviewed_at
"""


def list_submissions(status_filter: Optional[str], limit: int, offset: int) -> list[dict]:
    conditions = []
    params: list = []
    if status_filter:
        conditions.append("status = %s")
        params.append(status_filter)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT {_SUBMISSION_COLUMNS}
        FROM miklat_submissions
        {where_clause}
        ORDER BY submitted_at DESC
        LIMIT %s OFFSET %s;
    """
    params.extend([limit, offset])
    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def _get_submission_for_update(cur, submission_id: int) -> dict:
    cur.execute(
        f"SELECT {_SUBMISSION_COLUMNS} FROM miklat_submissions WHERE id = %s FOR UPDATE;",
        [submission_id],
    )
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    if row["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Submission is already '{row['status']}', expected 'pending'",
        )
    return row


def approve_submission(submission_id: int, reviewed_by: str) -> dict:
    with get_cursor(commit=True) as cur:
        submission = _get_submission_for_update(cur, submission_id)

        cur.execute(
            f"""
            INSERT INTO miklats (name, address, geom, type, capacity, description, is_verified)
            VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s, %s, TRUE)
            RETURNING id;
            """,
            [
                submission["name"], submission["address"],
                submission["lon"], submission["lat"],
                submission["type"] or "public_shelter",
                submission["capacity"], submission["comment"],
            ],
        )
        new_miklat_id = cur.fetchone()["id"]

        cur.execute(
            f"""
            UPDATE miklat_submissions
            SET status = 'approved', reviewed_by = %s, reviewed_at = now(), miklat_id = %s
            WHERE id = %s
            RETURNING {_SUBMISSION_COLUMNS};
            """,
            [reviewed_by, new_miklat_id, submission_id],
        )
        return cur.fetchone()


def reject_submission(submission_id: int, reviewed_by: str, rejection_reason: str) -> dict:
    with get_cursor(commit=True) as cur:
        _get_submission_for_update(cur, submission_id)
        cur.execute(
            f"""
            UPDATE miklat_submissions
            SET status = 'rejected', reviewed_by = %s, rejection_reason = %s, reviewed_at = now()
            WHERE id = %s
            RETURNING {_SUBMISSION_COLUMNS};
            """,
            [reviewed_by, rejection_reason, submission_id],
        )
        return cur.fetchone()


# ---------- miklat_reports: жалобы (публичное создание + admin-модерация) ----------
# SNS-триггер #2 (см. app/aws_client.py). Порядок операций тот же принцип,
# что в miklat-photos/app/crud.py::create_photo: сначала проверка/запись в
# БД, публикация в SNS — уже потом и best-effort (сбой уведомления не должен
# ронять сохранение самой жалобы).

_REPORT_COLUMNS = "id, miklat_id, issue_type, comment, contact, status, reported_at, reviewed_at"


def create_report(miklat_id: int, data, reporter_ip: Optional[str]) -> dict:
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT 1 FROM miklats WHERE id = %s;", [miklat_id])
        if cur.fetchone() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miklat not found")

        cur.execute(
            f"""
            INSERT INTO miklat_reports (miklat_id, issue_type, comment, contact, reporter_ip, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
            RETURNING {_REPORT_COLUMNS};
            """,
            [miklat_id, data.issue_type, data.comment, data.contact, reporter_ip],
        )
        report = cur.fetchone()

    try:
        aws_client.publish_report_notification(SNS_TOPIC_ARN, report)
    except Exception as exc:  # noqa: BLE001 - best-effort, см. docstring выше
        logger.warning("SNS publish failed for report_id=%s: %s", report["id"], exc)

    return report


def list_reports(status_filter: Optional[str], limit: int, offset: int) -> list[dict]:
    conditions = []
    params: list = []
    if status_filter:
        conditions.append("status = %s")
        params.append(status_filter)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT {_REPORT_COLUMNS}
        FROM miklat_reports
        {where_clause}
        ORDER BY reported_at DESC
        LIMIT %s OFFSET %s;
    """
    params.extend([limit, offset])
    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def set_report_status(report_id: int, new_status: str) -> dict:
    with get_cursor(commit=True) as cur:
        cur.execute(
            f"""
            UPDATE miklat_reports
            SET status = %s, reviewed_at = now()
            WHERE id = %s
            RETURNING {_REPORT_COLUMNS};
            """,
            [new_status, report_id],
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return row
