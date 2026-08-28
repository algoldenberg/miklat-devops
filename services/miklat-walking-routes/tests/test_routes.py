"""
Юнит-тесты на бизнес-логику эндпоинтов с "заглушкой" OSRM и БД —
ни реальный OSRM (карта Израиля, предобработка графа), ни Postgres
для них не нужны. Реальную интеграцию с живым OSRM проверяем руками
(см. README, раздел miklat-walking-routes) на машине с поднятым
docker-compose — там уже настоящая карта и настоящие расстояния.
"""

from fastapi.testclient import TestClient

from app import crud, osrm_client
from app.main import app

FAKE_OSRM_ROUTE = {
    "distance": 742.3,
    "duration": 561.4,
    "geometry": {"type": "LineString", "coordinates": [[34.78, 32.08], [34.7818, 32.0853]]},
}


def test_post_route_ok(monkeypatch):
    monkeypatch.setattr(osrm_client, "get_route", lambda coords: FAKE_OSRM_ROUTE)
    with TestClient(app) as client:
        response = client.post("/route", json={"from": {"lon": 34.78, "lat": 32.08}, "to": {"lon": 34.7818, "lat": 32.0853}})
    assert response.status_code == 200
    body = response.json()
    assert body["distance_m"] == 742.3
    assert body["duration_s"] == 561.4
    assert body["profile"] == "foot"
    assert body["geometry"]["type"] == "LineString"


def test_post_route_no_route_found(monkeypatch):
    def raise_no_route(coords):
        raise osrm_client.OSRMError("OSRM could not compute a route (code=NoRoute)", status_code=422)

    monkeypatch.setattr(osrm_client, "get_route", raise_no_route)
    with TestClient(app) as client:
        response = client.post("/route", json={"from": {"lon": 34.78, "lat": 32.08}, "to": {"lon": 34.79, "lat": 32.09}})
    assert response.status_code == 422


def test_post_route_osrm_unreachable(monkeypatch):
    def raise_unreachable(coords):
        raise osrm_client.OSRMError("OSRM routing engine is unreachable", status_code=503)

    monkeypatch.setattr(osrm_client, "get_route", raise_unreachable)
    with TestClient(app) as client:
        response = client.post("/route", json={"from": {"lon": 34.78, "lat": 32.08}, "to": {"lon": 34.79, "lat": 32.09}})
    assert response.status_code == 503


def test_route_to_miklat_resolves_coords_and_calls_osrm(monkeypatch):
    captured_coords = {}

    def fake_get_route(coords):
        captured_coords["value"] = coords
        return FAKE_OSRM_ROUTE

    monkeypatch.setattr(osrm_client, "get_route", fake_get_route)
    monkeypatch.setattr(crud, "get_miklat_coords", lambda miklat_id: (34.7818064, 32.0852997))

    with TestClient(app) as client:
        response = client.get("/route-to-miklat/12362?from_lon=34.78&from_lat=32.08")

    assert response.status_code == 200
    # порядок точек: сначала пользователь, потом укрытие
    assert captured_coords["value"] == [(34.78, 32.08), (34.7818064, 32.0852997)]


def test_route_to_miklat_not_found(monkeypatch):
    from fastapi import HTTPException

    def raise_not_found(miklat_id):
        raise HTTPException(status_code=404, detail=f"Miklat {miklat_id} not found")

    monkeypatch.setattr(crud, "get_miklat_coords", raise_not_found)
    with TestClient(app) as client:
        response = client.get("/route-to-miklat/999999?from_lon=34.78&from_lat=32.08")
    assert response.status_code == 404


def test_invalid_coordinates_rejected():
    with TestClient(app) as client:
        response = client.post("/route", json={"from": {"lon": 999, "lat": 32.08}, "to": {"lon": 34.79, "lat": 32.09}})
    assert response.status_code == 422
