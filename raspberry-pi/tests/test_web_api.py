import pytest

from homeauto.web import app as web

AUTH = {"Authorization": "Bearer test-token-0123456789abcdefghij"}


@pytest.fixture
def client():
    # HOMEAUTO_API_TOKEN is injected by conftest.py before the app is imported
    web._state.update(led=False, mode="manual")
    return web.app.test_client()


def test_status_requires_token(client):
    assert client.get("/api/status").status_code == 401
    assert client.get("/api/status", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_status_ok(client):
    response = client.get("/api/status", headers=AUTH)
    assert response.status_code == 200
    assert response.json["mode"] == "manual"


def test_led_toggle(client):
    response = client.post("/api/led", json={"state": "on"}, headers=AUTH)
    assert response.status_code == 200
    assert web._state["led"] is True


@pytest.mark.parametrize("payload", [{"state": "ON; rm -rf /"}, {"state": 1}, {}])
def test_led_rejects_invalid_input(client, payload):
    assert client.post("/api/led", json=payload, headers=AUTH).status_code == 400


def test_state_change_not_possible_via_get(client):
    assert client.get("/api/led", headers=AUTH).status_code == 405


def test_security_headers(client):
    response = client.get("/api/status", headers=AUTH)
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["Cache-Control"] == "no-store"
