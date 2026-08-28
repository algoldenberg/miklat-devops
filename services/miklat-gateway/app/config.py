"""
Конфигурация miklat-gateway — адреса всех остальных сервисов (внутри
docker-compose/k8s — их DNS-имена, задаются через env). Никакой БД и
никаких AWS-кредов здесь нет: gateway — чистый прокси, не хранит состояние
и не обращается ни к чему, кроме перечисленных сервисов по HTTP.
"""

import os

MIKLAT_SERVICE_URL = os.environ.get("MIKLAT_SERVICE_URL", "http://localhost:8001")
MIKLAT_COMMENTS_URL = os.environ.get("MIKLAT_COMMENTS_URL", "http://localhost:8002")
MIKLAT_ROUTES_URL = os.environ.get("MIKLAT_ROUTES_URL", "http://localhost:8003")
MIKLAT_WALKING_ROUTES_URL = os.environ.get("MIKLAT_WALKING_ROUTES_URL", "http://localhost:8004")
MIKLAT_PHOTOS_URL = os.environ.get("MIKLAT_PHOTOS_URL", "http://localhost:8005")

# Таймаут на запрос к любому downstream-сервису. Чуть выше, чем у остальных
# сервисов друг к другу (OSRM-запросы уже сами по себе не мгновенные).
UPSTREAM_TIMEOUT_S = float(os.environ.get("UPSTREAM_TIMEOUT_S", "15"))

SERVICE_URLS = {
    "miklat-service": MIKLAT_SERVICE_URL,
    "miklat-comments": MIKLAT_COMMENTS_URL,
    "miklat-routes": MIKLAT_ROUTES_URL,
    "miklat-walking-routes": MIKLAT_WALKING_ROUTES_URL,
    "miklat-photos": MIKLAT_PHOTOS_URL,
}
