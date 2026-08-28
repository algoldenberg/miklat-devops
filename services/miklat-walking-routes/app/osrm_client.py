"""
Тонкий клиент к OSRM HTTP API (сервис route, профиль foot).
Никакой обёртки-абстракции сверху не делаем — OSRM API стабилен и хорошо
задокументирован (http://project-osrm.org/docs/v5.24.0/api/#route-service).
"""

import httpx

from app.config import OSRM_BASE_URL, OSRM_PROFILE, OSRM_TIMEOUT_S


class OSRMError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def get_route(coordinates: list[tuple[float, float]]) -> dict:
    """
    coordinates — список (lon, lat) в порядке прохождения, минимум 2 точки.
    Возвращает первый маршрут из OSRM-ответа (routes[0]) как есть
    (distance, duration, geometry — GeoJSON, т.к. запрашиваем geometries=geojson).
    """
    if len(coordinates) < 2:
        raise ValueError("At least 2 coordinates are required")

    coord_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
    url = f"{OSRM_BASE_URL}/route/v1/{OSRM_PROFILE}/{coord_str}"
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}

    try:
        response = httpx.get(url, params=params, timeout=OSRM_TIMEOUT_S)
        response.raise_for_status()
    except httpx.RequestError as exc:
        raise OSRMError(f"OSRM routing engine is unreachable: {exc}", status_code=503) from exc
    except httpx.HTTPStatusError as exc:
        raise OSRMError(f"OSRM returned HTTP {exc.response.status_code}", status_code=502) from exc

    data = response.json()
    if data.get("code") != "Ok":
        raise OSRMError(
            f"OSRM could not compute a route (code={data.get('code')}, message={data.get('message')})",
            status_code=422,
        )
    return data["routes"][0]


def check_osrm() -> bool:
    """Дешёвая проверка живости OSRM для /ready — реальный крошечный маршрут."""
    try:
        get_route([(34.7800, 32.0800), (34.7810, 32.0810)])
        return True
    except OSRMError:
        return False
