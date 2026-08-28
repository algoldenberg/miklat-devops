"""
Бизнес-логика/SQL miklat-photos. Явные SQL-запросы, без ORM — тот же подход,
что в miklat-service/miklat-comments.

Порядок операций в create_photo() важен и сделан намеренно:
1. Проверка, что miklat_id существует — ДО обращения к S3 (не тратим вызов
   в облако на заведомо некорректный запрос, тот же принцип, что в тестах
   OSRM-сервисов: сначала дешёвая валидация, потом дорогой внешний вызов).
2. Заливка в S3 — если падает, вся операция считается неуспешной (503),
   потому что без файла в S3 запись в БД была бы бессмысленной.
3. Запись в БД (miklat_photos, status='pending') — отдельная транзакция от
   проверки существования (не держим соединение открытым на время сетевого
   вызова к S3).
4. SNS-уведомление о новом фото на модерации — best-effort (см. docstring
   app/aws_client.py): сбой публикации логируется, но НЕ считается ошибкой
   всего запроса — фото уже сохранено и видно в admin-очереди модерации.

Известное упрощение (ок для учебного проекта): если шаг 3 упадёт уже после
успешной заливки в S3 (шаг 2), объект в S3 останется "осиротевшим" — без
записи в БД. Реальная защита (двухфазная запись/cleanup-job) — за рамками
курса, отмечено здесь как осознанный trade-off.
"""

import logging
import uuid
from typing import Optional

from fastapi import HTTPException, status

from app import aws_client
from app.config import S3_BUCKET_NAME, SNS_TOPIC_ARN
from app.database import get_cursor

logger = logging.getLogger("miklat-photos.crud")

_PHOTO_COLUMNS = "id, miklat_id, s3_key, uploaded_by_ip, status, uploaded_at, reviewed_at"


def _miklat_exists(cur, miklat_id: int) -> bool:
    cur.execute("SELECT 1 FROM miklats WHERE id = %s;", [miklat_id])
    return cur.fetchone() is not None


def create_photo(
    miklat_id: int,
    content: bytes,
    content_type: str,
    extension: str,
    uploaded_by_ip: Optional[str],
) -> dict:
    with get_cursor() as cur:
        if not _miklat_exists(cur, miklat_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miklat not found")

    s3_key = f"photos/{miklat_id}/{uuid.uuid4().hex}{extension}"

    try:
        aws_client.upload_photo(S3_BUCKET_NAME, s3_key, content, content_type)
    except Exception as exc:  # noqa: BLE001 - любая ошибка boto3 здесь фатальна для запроса
        logger.error("S3 upload failed for miklat_id=%s key=%s: %s", miklat_id, s3_key, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is currently unavailable",
        ) from exc

    with get_cursor(commit=True) as cur:
        cur.execute(
            f"""
            INSERT INTO miklat_photos (miklat_id, s3_key, uploaded_by_ip, status)
            VALUES (%s, %s, %s, 'pending')
            RETURNING {_PHOTO_COLUMNS};
            """,
            [miklat_id, s3_key, uploaded_by_ip],
        )
        photo = cur.fetchone()

    try:
        aws_client.publish_photo_pending_notification(SNS_TOPIC_ARN, photo)
    except Exception as exc:  # noqa: BLE001 - см. docstring модуля: best-effort
        logger.warning("SNS publish failed for photo_id=%s: %s", photo["id"], exc)

    return photo


def list_public_photos(miklat_id: int, limit: int, offset: int) -> list[dict]:
    with get_cursor() as cur:
        if not _miklat_exists(cur, miklat_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Miklat not found")
        cur.execute(
            f"""
            SELECT {_PHOTO_COLUMNS}
            FROM miklat_photos
            WHERE miklat_id = %s AND status = 'approved'
            ORDER BY uploaded_at DESC
            LIMIT %s OFFSET %s;
            """,
            [miklat_id, limit, offset],
        )
        return cur.fetchall()


def list_admin_photos(status_filter: Optional[str], limit: int, offset: int) -> list[dict]:
    with get_cursor() as cur:
        if status_filter:
            cur.execute(
                f"""
                SELECT {_PHOTO_COLUMNS} FROM miklat_photos
                WHERE status = %s
                ORDER BY uploaded_at DESC
                LIMIT %s OFFSET %s;
                """,
                [status_filter, limit, offset],
            )
        else:
            cur.execute(
                f"""
                SELECT {_PHOTO_COLUMNS} FROM miklat_photos
                ORDER BY uploaded_at DESC
                LIMIT %s OFFSET %s;
                """,
                [limit, offset],
            )
        return cur.fetchall()


def _get_photo(cur, photo_id: int) -> dict:
    cur.execute(f"SELECT {_PHOTO_COLUMNS} FROM miklat_photos WHERE id = %s;", [photo_id])
    row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return row


def set_photo_status(photo_id: int, new_status: str) -> dict:
    with get_cursor(commit=True) as cur:
        cur.execute(
            f"""
            UPDATE miklat_photos
            SET status = %s, reviewed_at = now()
            WHERE id = %s
            RETURNING {_PHOTO_COLUMNS};
            """,
            [new_status, photo_id],
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return row


def delete_photo(photo_id: int) -> None:
    with get_cursor(commit=True) as cur:
        photo = _get_photo(cur, photo_id)
        cur.execute("DELETE FROM miklat_photos WHERE id = %s;", [photo_id])

    aws_client.delete_photo(S3_BUCKET_NAME, photo["s3_key"])
