"""
Prometheus-метрики miklat-gateway (Задание 5, Фаза 5).
Отдельный модуль — см. подробное объяснение в miklat-service/app/metrics.py.

У gateway нет собственного бизнес-действия (он только проксирует) — одна
бизнес-метрика уже покрыта другими сервисами (см. miklat-service,
miklat-comments, miklat-photos, miklat-routes, miklat-walking-routes).
Здесь достаточно /metrics + app_info + дефолтных HTTP-метрик
(request rate/errors/latency по проксируемым путям), которые
prometheus-fastapi-instrumentator даёт из коробки.
"""

import os

from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator

APP_INFO = Gauge(
    "app_info",
    "Информация о версии сервиса, отвечающего на запросы (значение всегда 1).",
    ["version", "git_sha", "release"],
)


def instrument(app, version: str) -> None:
    # ВАЖНО: должно быть вызвано до регистрации catch-all роута
    # `@app.api_route("/{full_path:path}", ...)` в main.py — иначе
    # /metrics перехватится проксированием вместо самого instrumentator'а
    # (Starlette матчит роуты в порядке регистрации).
    Instrumentator().instrument(app).expose(app, include_in_schema=False)
    APP_INFO.labels(
        version=version,
        git_sha=os.environ.get("GIT_SHA", "unknown"),
        release=os.environ.get("RELEASE_NAME", "unknown"),
    ).set(1)
