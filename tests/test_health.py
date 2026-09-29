from fastapi.testclient import TestClient


def test_health(tmp_path, monkeypatch):
    monkeypatch.setenv("ROWING_DB_PATH", str(tmp_path / "rowing-test.db"))
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert (tmp_path / "rowing-test.db").exists()
