"""
Prometheus-метрики miklat-photos (Задание 5, Фаза 5).
Отдельный модуль — см. подробное объяснение в miklat-service/app/metrics.py.
"""

import os

from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

APP_INFO = Gauge(
    "app_info",
    "Информация о версии сервиса, отвечающего на запросы (значение всегда 1).",
    ["version", "git_sha", "release"],
)

# Бизнес-метрика: реально сохранённые фото (после прохождения всех проверок
# в upload_photo — тип файла, размер, непустой контент, — не на каждый
# HTTP-запрос к эндпоинту).
PHOTOS_UPLOADED_TOTAL = Counter(
    "miklat_photos_uploaded_total",
    "Количество фото укрытий, реально сохранённых в S3 и БД.",
)


def instrument(app, version: str) -> None:
    Instrumentator().instrument(app).expose(app, include_in_schema=False)
    APP_INFO.labels(
        version=version,
        git_sha=os.environ.get("GIT_SHA", "unknown"),
        release=os.environ.get("RELEASE_NAME", "unknown"),
    ).set(1)
