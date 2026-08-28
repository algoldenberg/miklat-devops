"""
Таблица маршрутизации: чистая функция (метод, путь) -> ключ сервиса
(без сети, без сайд-эффектов) — специально вынесена отдельно от прокси-
логики, чтобы её было легко полностью покрыть тестами (см. tests/test_routing.py).

Почему не просто "префикс -> сервис": несколько сервисов используют
пересекающиеся пути (`/miklats/{id}/...` — то `miklat-comments`, то
`miklat-photos`, то `miklat-service`, в зависимости от последнего сегмента),
а `POST /route` определён СРАЗУ в двух сервисах (`miklat-routes` и
`miklat-walking-routes`) с разной семантикой (список точек vs ровно две
именованные). Наружу (через gateway) выставляется только один вариант —
двухточечный `POST /route` от miklat-walking-routes (это ровно то, что
покрывает сценарий "маршрут до одного укрытия" из фронтенда); собственный
generic `/route` у miklat-routes напрямую наружу не проксируется — он
избыточен по отношению к `/route-through-miklats` и двухточечному `/route`.
"""

from typing import Optional

_ADMIN_RESOURCE_TO_SERVICE = {
    "miklats": "miklat-service",
    "submissions": "miklat-service",
    "reports": "miklat-service",
    "comments": "miklat-comments",
    "photos": "miklat-photos",
}

_MIKLAT_SUBRESOURCE_TO_SERVICE = {
    "comments": "miklat-comments",
    "rating-summary": "miklat-comments",
    "photos": "miklat-photos",
    "reports": "miklat-service",
}


def resolve_target(method: str, path: str) -> Optional[str]:
    """Возвращает ключ сервиса (см. app.config.SERVICE_URLS) или None,
    если ни одно правило не подошло (вызывающий код должен ответить 404)."""
    segments = [s for s in path.strip("/").split("/") if s]
    if not segments:
        return None

    head = segments[0]

    if head == "admin":
        if len(segments) < 2:
            return None
        return _ADMIN_RESOURCE_TO_SERVICE.get(segments[1])

    if head == "route" and len(segments) == 1 and method.upper() == "POST":
        return "miklat-walking-routes"

    if head == "route-through-miklats" and len(segments) == 1 and method.upper() == "POST":
        return "miklat-routes"

    if head == "route-to-miklat":
        return "miklat-walking-routes"

    if head == "submissions" and len(segments) == 1 and method.upper() == "POST":
        # Публичная форма "добавить укрытие" на фронтенде (SNS-триггер #1a) —
        # не путать с /admin/submissions (модерация уже существующих заявок).
        return "miklat-service"

    if head == "miklats":
        if len(segments) in (1, 2):
            # "" (список) / "nearest" / "{id}" — все три обслуживает miklat-service
            return "miklat-service"
        if len(segments) == 3:
            return _MIKLAT_SUBRESOURCE_TO_SERVICE.get(segments[2])
        return None

    return None
