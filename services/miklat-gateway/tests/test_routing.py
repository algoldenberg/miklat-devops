"""
Полное покрытие таблицы маршрутизации (app.routing.resolve_target) — это
единственная по-настоящему нетривиальная логика в gateway (пути
пересекаются между сервисами, у /route два разных "владельца"), поэтому ей
уделено больше тестов, чем самому прокси-коду.
"""

import pytest

from app.routing import resolve_target


@pytest.mark.parametrize(
    "method,path,expected",
    [
        # miklat-service — базовые CRUD/поиск
        ("GET", "/miklats", "miklat-service"),
        ("GET", "/miklats/", "miklat-service"),
        ("GET", "/miklats/nearest", "miklat-service"),
        ("GET", "/miklats/12362", "miklat-service"),
        ("PATCH", "/miklats/12362", "miklat-service"),
        # miklat_id-под-ресурсы — расходятся по трём разным сервисам
        ("GET", "/miklats/1/comments", "miklat-comments"),
        ("POST", "/miklats/1/comments", "miklat-comments"),
        ("GET", "/miklats/1/rating-summary", "miklat-comments"),
        ("GET", "/miklats/1/photos", "miklat-photos"),
        ("POST", "/miklats/1/photos", "miklat-photos"),
        ("POST", "/miklats/1/reports", "miklat-service"),
        # маршруты — коллизия на /route разрешена в пользу walking-routes
        ("POST", "/route", "miklat-walking-routes"),
        ("GET", "/route-to-miklat/12362", "miklat-walking-routes"),
        ("POST", "/route-through-miklats", "miklat-routes"),
        # admin — по второму сегменту пути
        ("POST", "/admin/miklats", "miklat-service"),
        ("PATCH", "/admin/miklats/1", "miklat-service"),
        ("DELETE", "/admin/miklats/1", "miklat-service"),
        ("GET", "/admin/submissions", "miklat-service"),
        ("POST", "/admin/submissions/1/approve", "miklat-service"),
        ("POST", "/admin/submissions/1/reject", "miklat-service"),
        ("GET", "/admin/reports", "miklat-service"),
        ("POST", "/admin/reports/1/resolve", "miklat-service"),
        ("POST", "/admin/reports/1/invalid", "miklat-service"),
        ("PATCH", "/admin/comments/1", "miklat-comments"),
        ("DELETE", "/admin/comments/1", "miklat-comments"),
        ("GET", "/admin/photos", "miklat-photos"),
        ("POST", "/admin/photos/1/approve", "miklat-photos"),
        ("POST", "/admin/photos/1/reject", "miklat-photos"),
        ("DELETE", "/admin/photos/1", "miklat-photos"),
    ],
)
def test_resolve_target_known_routes(method, path, expected):
    assert resolve_target(method, path) == expected


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/"),
        ("GET", "/unknown"),
        ("GET", "/admin"),
        ("GET", "/admin/unknown-resource"),
        ("GET", "/miklats/1/unknown-subresource"),
        ("GET", "/route"),  # GET на /route не определён ни в одном сервисе — только POST
        ("DELETE", "/route"),
        ("GET", "/route-through-miklats"),  # только POST
    ],
)
def test_resolve_target_unknown_routes_return_none(method, path):
    assert resolve_target(method, path) is None
