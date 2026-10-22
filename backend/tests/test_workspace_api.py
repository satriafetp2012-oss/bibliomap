import pytest
from fastapi.testclient import TestClient

from bibliomap.api import workspaces
from bibliomap.main import app
from bibliomap.workspace.pipeline import StateCache
from bibliomap.workspace.store import WorkspaceStore


@pytest.fixture
def client(tmp_path):
    store = WorkspaceStore(tmp_path / "api.sqlite3")
    cache = StateCache(store)
    app.dependency_overrides[workspaces.get_store] = lambda: store
    app.dependency_overrides[workspaces.get_cache] = lambda: cache
    yield TestClient(app)
    app.dependency_overrides.clear()


def _upload(client, ws_id, fixture_bytes, name):
    return client.post(
        f"/api/workspaces/{ws_id}/imports/file", files={"file": (name, fixture_bytes(name))}
    )


def test_full_review_flow(client, fixture_bytes):
    ws = client.post("/api/workspaces", json={"name": "Helmet review"}).json()
    assert ws["name"] == "Helmet review"

    for name in ("wos_sample.txt", "scopus_sample.csv", "pubmed_sample.nbib"):
        assert _upload(client, ws["id"], fixture_bytes, name).status_code == 201

    summary = client.get(f"/api/workspaces/{ws['id']}").json()
    counts = summary["counts"]
    assert counts["identified"] == 6
    assert [i["label"] for i in summary["imports"]] == ["Web of Science", "Scopus", "PubMed"]
    assert counts["unique"] + counts["duplicates_removed"] == counts["identified"]

    pending = client.get(f"/api/workspaces/{ws['id']}/dedup/pending").json()
    for pair in pending["items"]:
        r = client.post(
            f"/api/workspaces/{ws['id']}/dedup/decisions",
            json={"record_a": pair["a"]["id"], "record_b": pair["b"]["id"], "same": True},
        )
        assert r.status_code == 204
    after = client.get(f"/api/workspaces/{ws['id']}").json()["counts"]
    assert after["pending_reviews"] == 0
    # Two distinct studies across all three databases.
    assert after["unique"] == 2

    r = client.put(f"/api/workspaces/{ws['id']}/filters", json={"document_types": ["article"]})
    assert r.json()["counts"]["kept"] == 1
    excluded = client.get(f"/api/workspaces/{ws['id']}/records", params={"status": "excluded"})
    assert excluded.json()["items"][0]["exclusion_reason"] == "document_type"
    kept = client.get(f"/api/workspaces/{ws['id']}/records").json()
    assert len(kept["items"][0]["merged"]["sources"]) == 3

    flow = client.get(f"/api/workspaces/{ws['id']}/prisma").json()
    assert flow["identified"] == 6
    assert flow["duplicates_removed"] == 4
    assert flow["automation_ineligible"] == 1
    assert flow["screened"] == 1
    assert flow["included"] is None


def test_pending_pair_view_and_undo(client, fixture_bytes):
    ws = client.post("/api/workspaces", json={}).json()
    _upload(client, ws["id"], fixture_bytes, "ris_sample.ris")
    _upload(client, ws["id"], fixture_bytes, "scopus_sample.csv")
    pending = client.get(f"/api/workspaces/{ws['id']}/dedup/pending").json()
    if pending["total"]:
        pair = pending["items"][0]
        assert {"title", "authors", "import_label", "doi"} <= pair["a"].keys()
        body = {"record_a": pair["a"]["id"], "record_b": pair["b"]["id"], "same": False}
        client.post(f"/api/workspaces/{ws['id']}/dedup/decisions", json=body)
        assert client.get(f"/api/workspaces/{ws['id']}/dedup/pending").json()["total"] == (
            pending["total"] - 1
        )
        client.delete(
            f"/api/workspaces/{ws['id']}/dedup/decisions",
            params={"record_a": body["record_a"], "record_b": body["record_b"]},
        )
        assert client.get(f"/api/workspaces/{ws['id']}/dedup/pending").json() == pending


def test_rename_and_delete_import(client, fixture_bytes):
    ws = client.post("/api/workspaces", json={}).json()
    imp = _upload(client, ws["id"], fixture_bytes, "ris_sample.ris").json()
    client.patch(f"/api/workspaces/{ws['id']}/imports/{imp['id']}", json={"label": "Embase"})
    flow = client.get(f"/api/workspaces/{ws['id']}/prisma").json()
    assert flow["identified_by_source"] == [{"label": "Embase", "count": 2}]
    assert client.delete(f"/api/workspaces/{ws['id']}/imports/{imp['id']}").status_code == 204
    assert client.delete(f"/api/workspaces/{ws['id']}/imports/{imp['id']}").status_code == 404
    assert client.get(f"/api/workspaces/{ws['id']}").json()["counts"]["identified"] == 0


def test_errors(client, fixture_bytes):
    assert client.get("/api/workspaces/does-not-exist").status_code == 404
    ws = client.post("/api/workspaces", json={}).json()
    bad = client.post(
        f"/api/workspaces/{ws['id']}/imports/file", files={"file": ("x.txt", b"hello\n")}
    )
    assert bad.status_code == 422
    r = client.post(
        f"/api/workspaces/{ws['id']}/dedup/decisions",
        json={"record_a": 1, "record_b": 999, "same": True},
    )
    assert r.status_code == 404
    r = client.put(f"/api/workspaces/{ws['id']}/filters", json={"year_from": 2024, "year_to": 2000})
    assert r.status_code == 422
