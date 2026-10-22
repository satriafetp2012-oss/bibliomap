import pytest

from bibliomap.schema import Author, Record, SourceFormat
from bibliomap.workspace.dedup import (
    MatchLevel,
    StoredRecord,
    find_duplicates,
    first_author_surname,
    normalize_title,
)
from bibliomap.workspace.merge import build_merged, merge_group

TITLE = "Road traffic injury among motorcycle riders in Indonesia: a population-based study"


def rec(
    id_: int,
    title: str = TITLE,
    *,
    doi: str | None = None,
    year: int | None = 2021,
    author: str | None = "Santoso, B",
    fmt: SourceFormat = SourceFormat.WOS,
    **extra,
) -> StoredRecord:
    record = Record(
        source_format=fmt,
        title=title,
        doi=doi,
        year=year,
        authors=[Author(name=author)] if author else [],
        **extra,
    )
    return StoredRecord(id=id_, import_id=1, record=record)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Road <i>traffic</i> injury: a study.", "road traffic injury a study"),
        ("Épidémiologie des accidents", "epidemiologie des accidents"),
        (None, ""),
    ],
)
def test_normalize_title(raw, expected):
    assert normalize_title(raw) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Santoso, Budi", "santoso"),
        ("Santoso B", "santoso"),
        ("Santoso BS", "santoso"),
        ("Budi Santoso", "santoso"),
        ("Jason R. C. Nurse", "nurse"),
        ("Müller J.", "muller"),
    ],
)
def test_first_author_surname(name, expected):
    record = Record(source_format=SourceFormat.RIS, title="x", authors=[Author(name=name)])
    assert first_author_surname(record) == expected


def test_same_doi_merges_automatically_across_formats():
    out = find_duplicates(
        [
            rec(1, doi="10.1/x"),
            rec(2, TITLE.upper() + ".", doi="10.1/x", author="Budi Santoso", fmt=SourceFormat.LENS),
        ]
    )
    assert out.groups == [[1, 2]]
    assert out.pending == []
    assert out.duplicates_removed == 1


def test_same_doi_different_title_goes_to_review():
    out = find_duplicates(
        [rec(1, doi="10.1/book"), rec(2, "A completely different chapter title", doi="10.1/book")]
    )
    assert out.groups == []
    assert [(p.a, p.b, p.level) for p in out.pending] == [(1, 2, MatchLevel.REVIEW)]
    assert "doi_equal" in out.pending[0].reasons


def test_identical_title_without_doi_merges_when_author_and_year_match():
    out = find_duplicates(
        [rec(1, doi="10.1/x"), rec(2, TITLE.replace(":", " -"), author="Santoso B")]
    )
    assert out.groups == [[1, 2]]


def test_small_typos_without_doi_merge_automatically():
    typo = TITLE.replace("motorcycle", "motorcylce").replace("population", "populaton")
    assert find_duplicates([rec(1), rec(2, typo)]).groups == [[1, 2]]


def test_reworded_title_without_doi_needs_review():
    out = find_duplicates([rec(1), rec(2, TITLE.replace("motorcycle", "motorbike"))])
    assert out.groups == []
    assert len(out.pending) == 1
    assert 92 <= out.pending[0].title_similarity < 98


def test_dropped_subtitle_needs_review():
    out = find_duplicates([rec(1), rec(2, TITLE.split(":")[0])])
    assert out.groups == []
    assert "title_prefix" in out.pending[0].reasons


def test_typo_at_start_is_still_found():
    out = find_duplicates(
        [rec(1), rec(2, "Rod" + TITLE[4:])] + [rec(i, f"Filler {i} " * 3) for i in range(3, 30)]
    )
    assert (1, 2) in {(p.a, p.b) for p in out.pending} or out.groups == [[1, 2]]


def test_different_years_or_authors_are_not_merged():
    assert find_duplicates([rec(1), rec(2, year=2015)]).groups == []
    out = find_duplicates([rec(1), rec(2, author="Wijaya, A")])
    assert out.groups == [] and out.pending == []


def test_different_dois_with_same_title_are_reviewed_not_merged():
    out = find_duplicates([rec(1, doi="10.1/preprint"), rec(2, doi="10.1/published")])
    assert out.groups == []
    assert out.pending[0].reasons[0] == "doi_different"


def test_short_generic_titles_never_auto_merge():
    out = find_duplicates([rec(1, "Editorial", author=None), rec(2, "Editorial", author=None)])
    assert out.groups == [] and out.pending == []


def test_decisions_override_rules():
    items = [
        rec(1, doi="10.1/x"),
        rec(2, doi="10.1/x"),
        rec(3, TITLE.replace("motorcycle", "motorbike")),
    ]
    # Reject the automatic DOI match, accept the review pair.
    out = find_duplicates(items, {(1, 2): False, (1, 3): True})
    assert out.groups == [[1, 3]]
    assert out.manual_merges == 1
    assert all((p.a, p.b) != (1, 2) for p in out.pending)


def test_pending_excludes_pairs_already_grouped():
    items = [rec(1, doi="10.1/x"), rec(2, doi="10.1/x"), rec(3)]
    out = find_duplicates(items)
    assert out.groups == [[1, 2, 3]]
    assert out.pending == []


def test_merge_prefers_complete_record_and_unions_lists():
    sparse = rec(1, doi="10.1/x", author_keywords=["helmet"], cited_by=3)
    full = rec(
        2,
        doi="10.1/x",
        fmt=SourceFormat.SCOPUS,
        abstract="Long abstract.",
        references=["Ref A", "Ref B"],
        author_keywords=["helmet", "Indonesia"],
        cited_by=9,
        volume="27",
    )
    merged = merge_group([sparse, full])

    assert merged.id == 1
    assert merged.record.source_format is SourceFormat.SCOPUS
    assert merged.record.abstract == "Long abstract."
    assert merged.record.author_keywords == ["helmet", "Indonesia"]
    assert merged.record.cited_by == 9
    assert [s.record_id for s in merged.sources] == [1, 2]
    assert {s.source_format for s in merged.sources} == {SourceFormat.WOS, SourceFormat.SCOPUS}


def test_build_merged_keeps_singletons():
    items = [
        rec(1, doi="10.1/x"),
        rec(2, doi="10.1/x"),
        rec(3, "Another study entirely about helmets"),
    ]
    merged = build_merged(items, find_duplicates(items).groups)
    assert [m.id for m in merged] == [1, 3]
    assert len(merged[0].sources) == 2


def test_scales_to_thousands_of_records():
    items = [
        rec(i, f"Study number {i} on topic {i * 7919 % 1000}", doi=f"10.1/{i}") for i in range(5000)
    ]
    items.append(rec(5000, "Study number 42 on topic 278", doi="10.1/42"))
    out = find_duplicates(items)
    assert out.groups == [[42, 5000]]
