"""
Prometheus-метрики miklat-service (Задание 5, Фаза 5).

Отдельный модуль (не внутри main.py и не внутри routers/*), чтобы роутеры
могли инкрементить счётчики без циклического импорта
app.main <-> app.routers.admin (main.py импортирует роутеры при старте,
роутеру нужен доступ к тем же объектам метрик — вынос в отдельный модуль
без обратных импортов на main.py решает это).

/metrics — отдельный эндпоинт (не /health и не /ready), добавляется
prometheus-fastapi-instrumentator. Он НЕ проксируется наружу: Ingress
(helm/miklat-app/templates/ingress.yaml) ведёт только на frontend, ни один
backend-сервис (включая этот) не выставлен через Ingress — то есть /metrics
физически недостижим снаружи кластера, доступен только Prometheus'у
изнутри (см. monitoring/service-monitors/).
"""

import os

from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

# gauge всегда равен 1 — сама версия/commit/release живут в лейблах, не в
# значении, чтобы дашборд мог узнать "какая версия сейчас отвечает" через
# group by (version, git_sha, release), а не через величину метрики.
APP_INFO = Gauge(
    "app_info",
    "Информация о версии сервиса, отвечающего на запросы (значение всегда 1).",
    ["version", "git_sha", "release"],
)

# Бизнес-метрика (Задание 5, п.4, кандидат из плана: "счётчик реально
# одобренных заявок на новое укрытие"). Инкрементится в
# app/routers/admin.py::approve_submission — там, где заявка реально
# переходит в статус approved, а не на каждый HTTP-запрос к эндпоинту.
SUBMISSIONS_APPROVED_TOTAL = Counter(
    "miklat_shelter_submissions_approved_total",
    "Количество заявок на новое укрытие, реально одобренных модератором.",
)


def instrument(app, version: str) -> None:
    """Вызывается один раз из main.py при старте приложения."""
    Instrumentator().instrument(app).expose(app, include_in_schema=False)
    APP_INFO.labels(
        version=version,
        git_sha=os.environ.get("GIT_SHA", "unknown"),
        release=os.environ.get("RELEASE_NAME", "unknown"),
    ).set(1)
