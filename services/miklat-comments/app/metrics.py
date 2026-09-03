"""
Prometheus-метрики miklat-comments (Задание 5, Фаза 5).
Отдельный модуль — см. подробное объяснение в miklat-service/app/metrics.py
(тот же паттерн, повторён одинаково во всех сервисах).
"""

import os

from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

APP_INFO = Gauge(
    "app_info",
    "Информация о версии сервиса, отвечающего на запросы (значение всегда 1).",
    ["version", "git_sha", "release"],
)

# Бизнес-метрика: реально опубликованные комментарии (POST .../comments).
COMMENTS_POSTED_TOTAL = Counter(
    "miklat_comments_posted_total",
    "Количество комментариев к укрытиям, реально созданных пользователями.",
)


def instrument(app, version: str) -> None:
    Instrumentator().instrument(app).expose(app, include_in_schema=False)
    APP_INFO.labels(
        version=version,
        git_sha=os.environ.get("GIT_SHA", "unknown"),
        release=os.environ.get("RELEASE_NAME", "unknown"),
    ).set(1)
