import importlib

from fastapi.testclient import TestClient


def test_user_session_throw_advice_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("DARTBOARD_DB_PATH", str(tmp_path / "api.db"))
    api = importlib.import_module("src.dart_board.api")
    api = importlib.reload(api)

    client = TestClient(api.app)

    r = client.post("/users", json={"user_id": "u1", "name": "Matt"})
    assert r.status_code == 200

    r = client.post("/sessions", json={"session_id": "s1", "user_id": "u1", "source_ref": "file.mp4"})
    assert r.status_code == 200

    r = client.post(
        "/throws",
        json={
            "user_id": "u1",
            "session_id": "s1",
            "x_norm": 0.42,
            "y_norm": 0.33,
            "confidence": 0.88,
        },
    )
    assert r.status_code == 200

    r = client.get("/advice/u1/40")
    assert r.status_code == 200
    payload = r.json()
    assert payload["can_finish"] is True
    assert ["D20"] in payload["combinations"]

    r = client.get("/heatmap/u1.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"

    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]

    r = client.get("/capture/status")
    assert r.status_code == 200
    status = r.json()
    assert status["running"] is False


def test_capture_disabled_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("DARTBOARD_DB_PATH", str(tmp_path / "api-disabled.db"))
    monkeypatch.setenv("DARTBOARD_CAPTURE_ENABLED", "false")
    api = importlib.import_module("src.dart_board.api")
    api = importlib.reload(api)

    client = TestClient(api.app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["capture_enabled"] == "false"

    r = client.get("/capture/status")
    assert r.status_code == 200
    assert r.json()["last_error"] == "capture disabled in current deployment"

    r = client.get("/calibration/status")
    assert r.status_code == 200
    assert r.json()["calibrated"] is False

    r = client.post(
        "/calibration/set",
        json={"src_points": [[10, 10], [110, 10], [110, 110], [10, 110]]},
    )
    assert r.status_code == 200
    assert r.json()["calibrated"] is True

    r = client.post("/calibration/clear")
    assert r.status_code == 200
    assert r.json()["calibrated"] is False


def test_api_key_enforcement(tmp_path, monkeypatch):
    monkeypatch.setenv("DARTBOARD_DB_PATH", str(tmp_path / "api-key.db"))
    monkeypatch.setenv("DARTBOARD_API_KEY", "secret123")
    api = importlib.import_module("src.dart_board.api")
    api = importlib.reload(api)

    client = TestClient(api.app)
    r = client.get("/health")
    assert r.status_code == 200

    r = client.post("/users", json={"user_id": "u2", "name": "Matt"})
    assert r.status_code == 401

    r = client.post(
        "/users",
        json={"user_id": "u2", "name": "Matt"},
        headers={"x-api-key": "secret123"},
    )
    assert r.status_code == 200
