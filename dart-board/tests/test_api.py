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
