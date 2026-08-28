"""Конфигурация miklat-routes — только через переменные окружения."""

import os

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://miklat:miklat_dev_password@localhost:5432/miklat",
)

OSRM_BASE_URL: str = os.environ.get("OSRM_BASE_URL", "http://localhost:5001")

# Тот же граф/сервис OSRM, что и у miklat-walking-routes (один общий контейнер
# osrm-backend с пешеходным профилем — car в проде не прижился, см. progress-лог).
OSRM_PROFILE = "foot"

OSRM_TIMEOUT_S = 15.0

MAX_WAYPOINTS = 15
