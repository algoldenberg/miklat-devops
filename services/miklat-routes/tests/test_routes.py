"""
Юнит-тесты бизнес-логики с "заглушкой" OSRM и БД (см. пояснение в
miklat-walking-routes/tests/test_routes.py — тот же подход).
"""

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import crud, osrm_client
from app.main import app

FAKE_OSRM_MULTI_ROUTE = {
    "distance": 1850.0,
    "duration": 1400.0,
    "legs": [
        {"distance": 900.0, "duration": 680.0},
        {"distance": 950.0, "duration": 720.0},
    ],
    "geometry": {"type": "LineString", "coordinates": [[34.78, 32.08], [34.79, 32.085], [34.80, 32.09]]},
}


def test_route_generic_waypoints_ok(monkeypatch):
    monkeypatch.setattr(osrm_client, "get_route", lambda coords: FAKE_OSRM_MULTI_ROUTE)
    with TestClient(app) as client:
        response = client.post(
            "/route",
            json={"waypoints": [{"lon": 34.78, "lat": 32.08}, {"lon": 34.79, "lat": 32.085}, {"lon": 34.80, "lat": 32.09}]},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["total_distance_m"] == 1850.0
    assert len(body["legs"]) == 2
    assert body["legs"][0]["distance_m"] == 900.0


def test_route_single_waypoint_rejected():
    with TestClient(app) as client:
        response = client.post("/route", json={"waypoints": [{"lon": 34.78, "lat": 32.08}]})
    assert response.status_code == 422


def test_route_through_miklats_ok(monkeypatch):
    captured = {}

    def fake_coords(ids):
        captured["ids"] = ids
        return {68: (34.8142548, 32.0834292), 1: (34.795009, 32.049499)}

    def fake_get_route(coords):
        captured["coords"] = coords
        return FAKE_OSRM_MULTI_ROUTE

    monkeypatch.setattr(crud, "get_miklats_coords", fake_coords)
    monkeypatch.setattr(osrm_client, "get_route", fake_get_route)

    with TestClient(app) as client:
        response = client.post("/route-through-miklats", json={"miklat_ids": [68, 1]})

    assert response.status_code == 200
    body = response.json()
    assert body["miklat_ids"] == [68, 1]
    # порядок сохранён как в запросе, а не как вернул dict со сгруппированными координатами
    assert captured["coords"] == [(34.8142548, 32.0834292), (34.795009, 32.049499)]


def test_route_through_miklats_with_start(monkeypatch):
    captured = {}

    def fake_get_route(coords):
        captured["coords"] = coords
        return FAKE_OSRM_MULTI_ROUTE

    monkeypatch.setattr(crud, "get_miklats_coords", lambda ids: {68: (34.8142548, 32.0834292)})
    monkeypatch.setattr(osrm_client, "get_route", fake_get_route)

    with TestClient(app) as client:
        response = client.post(
            "/route-through-miklats",
            json={"miklat_ids": [68], "start": {"lon": 34.78, "lat": 32.08}},
        )

    assert response.status_code == 200
    assert captured["coords"] == [(34.78, 32.08), (34.8142548, 32.0834292)]


def test_route_through_miklats_single_id_no_start_rejected():
    with TestClient(app) as client:
        response = client.post("/route-through-miklats", json={"miklat_ids": [68]})
    assert response.status_code == 422


def test_route_through_miklats_missing_id(monkeypatch):
    def raise_not_found(ids):
        raise HTTPException(status_code=404, detail=f"Miklat(s) not found: {ids}")

    monkeypatch.setattr(crud, "get_miklats_coords", raise_not_found)
    with TestClient(app) as client:
        response = client.post("/route-through-miklats", json={"miklat_ids": [999999, 1]})
    assert response.status_code == 404
