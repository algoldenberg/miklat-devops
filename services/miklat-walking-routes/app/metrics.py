"""
Prometheus-метрики miklat-walking-routes (Задание 5, Фаза 5).
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

# Бизнес-метрика: успешно построенные пешие маршруты до укрытия — основной
# пользовательский сценарий приложения (см. комментарий у
# get_route_to_miklat в app/routers/routes.py).
WALKING_ROUTES_CALCULATED_TOTAL = Counter(
    "miklat_walking_routes_calculated_total",
    "Количество пеших маршрутов, успешно построенных через OSRM.",
)


def instrument(app, version: str) -> None:
    Instrumentator().instrument(app).expose(app, include_in_schema=False)
    APP_INFO.labels(
        version=version,
        git_sha=os.environ.get("GIT_SHA", "unknown"),
        release=os.environ.get("RELEASE_NAME", "unknown"),
    ).set(1)
