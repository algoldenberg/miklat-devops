"""
Prometheus-метрики miklat-routes (Задание 5, Фаза 5).
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

# Бизнес-метрика (кандидат из плана: "счётчик успешно построенных
# маршрутов"). Инкрементится в _build_route только после успешного ответа
# от OSRM — ошибки OSRM (osrm_client.OSRMError) поднимаются раньше и сюда
# не доходят.
ROUTES_CALCULATED_TOTAL = Counter(
    "miklat_routes_calculated_total",
    "Количество маршрутов через укрытия, успешно построенных через OSRM.",
)


def instrument(app, version: str) -> None:
    Instrumentator().instrument(app).expose(app, include_in_schema=False)
    APP_INFO.labels(
        version=version,
        git_sha=os.environ.get("GIT_SHA", "unknown"),
        release=os.environ.get("RELEASE_NAME", "unknown"),
    ).set(1)
