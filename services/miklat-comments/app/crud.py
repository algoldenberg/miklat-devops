"""SQL-запросы miklat-comments. Явные, без ORM (тот же подход, что в miklat-service)."""


from fastapi import HTTPException, status

from app.database import get_cursor

_COMMENT_COLUMNS = "id, miklat_id, username, comment, rating, created_at, updated_at"


def _miklat_exists(cur, miklat_id: int) -> bool:
    cur.execute("SELECT 1 FROM miklats WHERE id = %s;", [miklat_id])
    return cur.fetchone() is not None


def list_comments(miklat_id: int, limit: int, offset: int) -> list[dict]:
    with get_cursor() as cur:
        if not _miklat_exists(cur, miklat_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miklat not found")
        cur.execute(
            f"""
            SELECT {_COMMENT_COLUMNS}
            FROM miklat_comments
            WHERE miklat_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s;
            """,
            [miklat_id, limit, offset],
        )
        return cur.fetchall()


def create_comment(miklat_id: int, data) -> dict:
    with get_cursor(commit=True) as cur:
        if not _miklat_exists(cur, miklat_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miklat not found")
        cur.execute(
            f"""
            INSERT INTO miklat_comments (miklat_id, username, comment, rating)
            VALUES (%s, %s, %s, %s)
            RETURNING {_COMMENT_COLUMNS};
            """,
            [miklat_id, data.username or "Anonymous", data.comment, data.rating],
        )
        return cur.fetchone()


def rating_summary(miklat_id: int) -> dict:
    with get_cursor() as cur:
        if not _miklat_exists(cur, miklat_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miklat not found")
        cur.execute(
            """
            SELECT
                COUNT(*) AS comments_count,
                COUNT(rating) AS ratings_count,
                AVG(rating)::float AS average_rating
            FROM miklat_comments
            WHERE miklat_id = %s;
            """,
            [miklat_id],
        )
        row = cur.fetchone()
    return {
        "miklat_id": miklat_id,
        "comments_count": row["comments_count"],
        "ratings_count": row["ratings_count"],
        "average_rating": round(row["average_rating"], 2) if row["average_rating"] is not None else None,
    }


# ---------- admin moderation ----------

def update_comment(comment_id: int, data) -> dict:
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return _get_comment(comment_id)

    set_clauses = [f"{column} = %s" for column in fields]
    params = list(fields.values())
    set_clauses.append("updated_at = now()")
    params.append(comment_id)

    query = f"""
        UPDATE miklat_comments
        SET {', '.join(set_clauses)}
        WHERE id = %s
        RETURNING {_COMMENT_COLUMNS};
    """
    with get_cursor(commit=True) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return row


def _get_comment(comment_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute(f"SELECT {_COMMENT_COLUMNS} FROM miklat_comments WHERE id = %s;", [comment_id])
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return row


def delete_comment(comment_id: int) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM miklat_comments WHERE id = %s RETURNING id;", [comment_id])
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")