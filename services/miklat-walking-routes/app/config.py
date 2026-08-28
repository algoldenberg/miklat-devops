"""Конфигурация miklat-walking-routes — только через переменные окружения."""

import os

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://miklat:miklat_dev_password@localhost:5432/miklat",
)

# Базовый URL сервиса OSRM (контейнер osrm-backend, http-профиль пешехода).
# В докер-сети сервис называется "osrm" (см. docker-compose.yml).
OSRM_BASE_URL: str = os.environ.get("OSRM_BASE_URL", "http://localhost:5001")

# У нас только пешеходный профиль (в проде driving не заработал для этого
# сценария и был заброшен — см. miklat-progress.md) — сознательно не делаем
# профиль настраиваемым, чтобы не тащить car.lua/граф, который не используется.
OSRM_PROFILE = "foot"

OSRM_TIMEOUT_S = 10.0
