import pytest

from bibliomap.parsers import parse_bytes
from bibliomap.schema import DocumentType, SourceFormat
from bibliomap.workspace.filters import ExclusionReason, FilterSpec
from bibliomap.workspace.pipeline import StateCache, compute_state
from bibliomap.workspace.store import WorkspaceNotFoundError, WorkspaceStore


@pytest.fixture
def store(tmp_path):
    return WorkspaceStore(tmp_path / "db" / "test.sqlite3")


def _import(store, ws_id, fixture_bytes, name, **kwargs):
    result = parse_bytes(fixture_bytes(name))
    return store.add_import(
        ws_id,
        source_format=result.source_format,
        records=result.records,
        warnings=result.warnings,
        origin=name,
        **kwargs,
    )


def test_workspace_lifecycle(store, fixture_bytes):
    ws = store.create_workspace("Helmet review")
    assert len(ws.id) >= 20 and ws.version == 0

    wos = _import(store, ws.id, fixture_bytes, "wos_sample.txt")
    ris = _import(store, ws.id, fixture_bytes, "ris_sample.ris")
    assert wos.label == "Web of Science"
    assert ris.label == "ris_sample.ris"  # RIS can be any database
    assert store.get_workspace(ws.id).version == 2
    assert len(store.load_records(ws.id)) == 4

    store.rename_import(ws.id, ris.id, "Scopus")
    assert store.list_imports(ws.id)[1].label == "Scopus"

    assert store.delete_import(ws.id, ris.id)
    assert len(store.load_records(ws.id)) == 2


def test_unknown_workspace_raises(store):
    with pytest.raises(WorkspaceNotFoundError):
        store.get_workspace("nope")


def test_pipeline_dedups_across_databases_and_builds_prisma(store, fixture_bytes):
    ws = store.create_workspace("x")
    # The WoS, RIS, PubMed and Scopus fixtures describe the same 2 studies.
    for name in ("wos_sample.txt", "ris_sample.ris", "pubmed_sample.nbib", "scopus_sample.csv"):
        _import(store, ws.id, fixture_bytes, name)

    state = compute_state(store, ws.id)
    assert state.prisma.identified == 8
    assert {s.label for s in state.prisma.identified_by_source} == {
        "Web of Science",
        "ris_sample.ris",
        "PubMed",
        "Scopus",
    }
    # 4 copies of the DOI'd article collapse; the conference paper copies
    # (no DOI in some sources) merge or wait for review.
    article = next(m for m in state.merged if m.record.doi == "10.5555/ip-2020-0001")
    assert len(article.sources) == 4
    assert {s.source_format for s in article.sources} == {
        SourceFormat.WOS,
        SourceFormat.RIS,
        SourceFormat.PUBMED,
        SourceFormat.SCOPUS,
    }
    assert state.prisma.duplicates_removed == state.dedup.duplicates_removed
    assert state.prisma.screened == len(state.merged)
    assert state.prisma.identified == state.prisma.screened + state.prisma.duplicates_removed


def test_decisions_and_filters_update_state(store, fixture_bytes):
    ws = store.create_workspace("x")
    for name in ("wos_sample.txt", "scopus_sample.csv"):
        _import(store, ws.id, fixture_bytes, name)
    cache = StateCache(store)
    before = cache.get(ws.id)
    assert cache.get(ws.id) is before  # cached for the same version

    # Force the two conference-paper copies apart, then together.
    a, b = (r.id for r in before.records.values() if "Helmet law" in r.record.title)
    store.set_decision(ws.id, b, a, same=False)
    apart = cache.get(ws.id)
    assert apart is not before
    assert all(not {a, b} <= set(g) for g in apart.dedup.groups)
    store.set_decision(ws.id, a, b, same=True)
    assert any({a, b} <= set(g) for g in cache.get(ws.id).dedup.groups)
    store.delete_decision(ws.id, a, b)
    assert (a, b) not in store.decisions(ws.id)

    store.set_filters(ws.id, FilterSpec(document_types=[DocumentType.ARTICLE]))
    filtered = cache.get(ws.id)
    assert filtered.prisma.automation_ineligible >= 1
    assert ExclusionReason.DOCUMENT_TYPE in filtered.prisma.automation_ineligible_by_reason
    assert all(m.record.document_type is DocumentType.ARTICLE for m in filtered.filtered.kept)


def test_deleting_import_drops_its_decisions(store, fixture_bytes):
    ws = store.create_workspace("x")
    _import(store, ws.id, fixture_bytes, "wos_sample.txt")
    ris = _import(store, ws.id, fixture_bytes, "ris_sample.ris")
    ids = [r.id for r in store.load_records(ws.id)]
    store.set_decision(ws.id, ids[0], ids[-1], same=True)
    store.delete_import(ws.id, ris.id)
    assert store.decisions(ws.id) == {}
