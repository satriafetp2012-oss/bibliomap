import pytest
from fastapi.testclient import TestClient

from bibliomap.api import imports
from bibliomap.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize(
    ("name", "fmt", "count"),
    [
        ("wos_sample.txt", "wos", 2),
        ("scopus_sample.csv", "scopus", 2),
        ("ris_sample.ris", "ris", 2),
        ("pubmed_sample.nbib", "pubmed", 2),
    ],
)
def test_preview_auto_detects(fixture_bytes, name, fmt, count):
    response = client.post("/api/imports/preview", files={"file": (name, fixture_bytes(name))})

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == name
    assert body["record_count"] == count
    assert body["result"]["source_format"] == fmt


def test_preview_with_explicit_format(fixture_bytes):
    response = client.post(
        "/api/imports/preview",
        params={"source_format": "ris"},
        files={"file": ("x.txt", fixture_bytes("ris_sample.ris"))},
    )
    assert response.json()["result"]["source_format"] == "ris"


def test_unknown_format_returns_422():
    response = client.post("/api/imports/preview", files={"file": ("x.txt", b"just some text\n")})
    assert response.status_code == 422
    assert "tidak dikenali" in response.json()["detail"]


def test_empty_file_returns_422():
    response = client.post("/api/imports/preview", files={"file": ("x.txt", b"  \n")})
    assert response.status_code == 422


def test_oversized_file_returns_413(monkeypatch):
    monkeypatch.setattr(imports, "MAX_UPLOAD_BYTES", 10)
    response = client.post(
        "/api/imports/preview", files={"file": ("x.txt", b"PMID- 1\nTI  - long title\n")}
    )
    assert response.status_code == 413
