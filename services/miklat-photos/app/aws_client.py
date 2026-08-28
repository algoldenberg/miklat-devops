"""
Тонкий клиент к AWS S3 (хранение фото) и SNS (уведомление о модерации).

Сознательно вынесено в отдельный модуль с простыми функциями (а не разбросано
по crud.py/routers) по тому же принципу, что и app/osrm_client.py в
miklat-routes / miklat-walking-routes: реальную инфраструктуру (там — OSRM,
здесь — AWS) невозможно поднять в песочнице Claude (нет сети до AWS, только
у пользователя), поэтому бизнес-логика тестируется через monkeypatch именно
этих функций — они единственная точка, где сервис реально "выходит наружу".

Ленивая инициализация клиентов (как lazy DB pool в database.py): если
AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY не заданы, boto3.client(...) всё
равно создаётся успешно (креды подтягиваются лениво при первом реальном
вызове) — падать сервис начнёт только на самом вызове upload/publish, что
позволяет /health отвечать независимо от настроенности AWS.
"""

import json
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from app.config import AWS_REGION, PHOTO_URL_EXPIRY_SECONDS

logger = logging.getLogger("miklat-photos.aws")

_s3_client = None
_sns_client = None


def _s3():
    global _s3_client
    if _s3_client is None:
        # Явный региональный endpoint обязателен для "opt-in"-регионов AWS
        # (запущенных после 2019, например il-central-1) — без него boto3 в
        # некоторых операциях (в частности generate_presigned_url) строит
        # запрос на старый глобальный s3.amazonaws.com, а такие регионы его
        # не поддерживают: AWS отвечает IllegalLocationConstraintException.
        # Для "классических" регионов (us-east-1, eu-west-1 и т.п.) этот же
        # endpoint_url тоже корректен, так что код остаётся портируемым.
        _s3_client = boto3.client(
            "s3",
            region_name=AWS_REGION,
            endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com",
        )
    return _s3_client


def _sns():
    global _sns_client
    if _sns_client is None:
        _sns_client = boto3.client("sns", region_name=AWS_REGION)
    return _sns_client


def upload_photo(bucket: str, key: str, content: bytes, content_type: str) -> None:
    """Заливает файл в S3. Поднимает исключение как есть — вызывающий код
    (crud.create_photo) решает, что с этим делать (см. там же)."""
    _s3().put_object(Bucket=bucket, Key=key, Body=content, ContentType=content_type)


def delete_photo(bucket: str, key: str) -> None:
    """Best-effort удаление объекта из S3 (используется при admin DELETE).
    Отсутствие объекта не считается ошибкой — цель вызова достигнута."""
    try:
        _s3().delete_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        logger.warning("S3 delete_object failed for key=%s: %s", key, exc)


def generate_presigned_url(bucket: str, key: str, expiry_seconds: int = PHOTO_URL_EXPIRY_SECONDS) -> str:
    """Временная ссылка на просмотр фото. Бакет не публичный (IAM-политика
    ограничена s3:PutObject/GetObject — см. work-plan, Фаза 2/3), поэтому
    доступ к каждому фото сервис выдаёт сам, а не через bucket policy."""
    return _s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiry_seconds,
    )


def publish_photo_pending_notification(topic_arn: str, photo: dict) -> None:
    """SNS-триггер #1b (см. db/001_init.sql, combined-project-overview.md):
    новое фото ожидает модерации. Публикуется в тот же Topic
    `miklat-notifications`, что и заявки на новые укрытия (#1a) и жалобы (#2).

    Отдельная функция (не встроено в create_photo) специально, чтобы её было
    легко monkeypatch-нуть в тестах и чтобы сбой публикации был явно
    изолирован от записи в БД (см. вызывающий код в crud.py — сбой SNS не
    должен ронять весь аплоуд)."""
    message = {
        "event": "photo_pending_moderation",
        "photo_id": photo["id"],
        "miklat_id": photo["miklat_id"],
        "s3_key": photo["s3_key"],
        "uploaded_at": photo["uploaded_at"].isoformat()
        if isinstance(photo["uploaded_at"], datetime)
        else str(photo["uploaded_at"]),
    }
    _sns().publish(
        TopicArn=topic_arn,
        Subject="miklat-devops: новое фото ожидает модерации",
        Message=json.dumps(message, ensure_ascii=False),
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
