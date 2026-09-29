import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ROWING_DB_PATH", str(tmp_path / "rowing-test.db"))
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
