import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.intake.catalog import load_sample
from app.modules.runs.pipeline import calculate


@pytest.fixture(scope="session")
def package():
    return load_sample("mixed")


@pytest.fixture(scope="session")
def snapshot(package):
    return calculate(package)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "review.sqlite3", seed=False)) as test:
        yield test


@pytest.fixture
def run_base(client):
    response = client.post("/api/runs", json={"sample": "mixed"})
    assert response.status_code == 201, response.text
    return "/api/runs/" + response.json()["manifest"]["run_id"]
