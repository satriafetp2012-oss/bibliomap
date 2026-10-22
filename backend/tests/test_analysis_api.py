import pytest
from fastapi.testclient import TestClient

from bibliomap.api import workspaces
from bibliomap.main import app
from bibliomap.workspace.pipeline import StateCache
from bibliomap.workspace.store import WorkspaceStore


@pytest.fixture
def client(tmp_path):
    store = WorkspaceStore(tmp_path / "analysis.sqlite3")
    cache = StateCache(store)
    app.dependency_overrides[workspaces.get_store] = lambda: store
    app.dependency_overrides[workspaces.get_cache] = lambda: cache
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def workspace(client, fixture_bytes):
    ws = client.post("/api/workspaces", json={"name": "Analysis"}).json()
    for name in ("wos_sample.txt", "scopus_sample.csv", "pubmed_sample.nbib"):
        client.post(
            f"/api/workspaces/{ws['id']}/imports/file", files={"file": (name, fixture_bytes(name))}
        )
    return ws["id"]


def test_statistics_endpoint(client, workspace):
    body = client.get(f"/api/workspaces/{workspace}/analysis/statistics").json()

    overview = body["overview"]
    assert overview["documents"] >= 1
    assert overview["year_min"] is not None
    assert {"documents", "sources", "authors", "mean_citations"} <= overview.keys()
    assert isinstance(body["top_authors"], list)
    assert {"key", "label", "documents", "citations", "h_index"} <= body["top_authors"][0].keys()
    assert "rows" in body["lotka"] and "exponent" in body["lotka"]
    assert "zone_sources" in body["bradford"]


def test_statistics_respects_limit(client, workspace):
    body = client.get(
        f"/api/workspaces/{workspace}/analysis/statistics", params={"limit": 5}
    ).json()
    assert len(body["top_authors"]) <= 5


def test_network_units_endpoint(client, workspace):
    units = client.get(f"/api/workspaces/{workspace}/analysis/network-units").json()
    assert units["co_occurrence"] == ["keyword", "index_keyword"]
    assert "author" in units["co_authorship"]


def test_science_map_endpoint(client, workspace):
    response = client.post(
        f"/api/workspaces/{workspace}/analysis/map",
        json={"type": "co_authorship", "unit": "author", "min_occurrences": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "co_authorship"
    assert body["nodes"]
    node = body["nodes"][0]
    assert {"id", "label", "x", "y", "cluster", "weight"} <= node.keys()
    assert body["clusters"] >= 1
    assert body["truncated_from"] is None


def test_map_is_cached_and_deterministic(client, workspace):
    body = {"type": "co_authorship", "unit": "author", "min_occurrences": 1}
    url = f"/api/workspaces/{workspace}/analysis/map"
    first = client.post(url, json=body).json()
    second = client.post(url, json=body).json()
    assert first == second


def test_map_truncates_large_networks(client, workspace):
    body = client.post(
        f"/api/workspaces/{workspace}/analysis/map",
        json={"type": "co_authorship", "unit": "author", "min_occurrences": 1, "max_nodes": 2},
    ).json()
    assert len(body["nodes"]) == 2
    assert body["truncated_from"] is not None and body["truncated_from"] > 2


def test_map_reflects_filters(client, workspace):
    url = f"/api/workspaces/{workspace}/analysis/map"
    body = {"type": "co_occurrence", "unit": "keyword", "min_occurrences": 1}
    before = client.post(url, json=body).json()
    client.put(f"/api/workspaces/{workspace}/filters", json={"year_from": 2100})
    after = client.post(url, json=body).json()
    assert after["nodes"] == []
    assert before["nodes"] != []


def test_unknown_workspace_returns_404(client):
    assert client.get("/api/workspaces/nope/analysis/statistics").status_code == 404
    assert client.post("/api/workspaces/nope/analysis/map", json={}).status_code == 404
