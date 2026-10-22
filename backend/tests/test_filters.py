import pytest

from bibliomap.parsers._common import normalize_language
from bibliomap.schema import DocumentType, Record, SourceFormat
from bibliomap.workspace.filters import ExclusionReason, FilterSpec, apply_filters, exclusion_reason
from bibliomap.workspace.merge import MergedRecord


def item(**fields) -> MergedRecord:
    record = Record(source_format=SourceFormat.WOS, title="T", **fields)
    return MergedRecord(id=1, record=record, sources=[])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("English", "en"),
        ("eng", "en"),
        ("EN", "en"),
        ("Indonesian", "id"),
        ("klingon", "klingon"),
        (None, None),
    ],
)
def test_normalize_language(raw, expected):
    assert normalize_language(raw) == expected


@pytest.mark.parametrize(
    ("fields", "spec", "expected"),
    [
        ({"year": 2010}, {"year_from": 2015}, ExclusionReason.YEAR),
        ({"year": 2026}, {"year_to": 2025}, ExclusionReason.YEAR),
        ({"year": None}, {"year_from": 2015}, None),  # unknown values are kept
        (
            {"document_type": DocumentType.LETTER},
            {"document_types": ["article", "review"]},
            ExclusionReason.DOCUMENT_TYPE,
        ),
        ({"language": "eng"}, {"languages": ["en"]}, None),
        ({"language": "Spanish"}, {"languages": ["en", "id"]}, ExclusionReason.LANGUAGE),
        ({"cited_by": 2}, {"min_cited_by": 5}, ExclusionReason.CITATIONS),
        ({"cited_by": None}, {"min_cited_by": 5}, None),
        ({"abstract": None}, {"require_abstract": True}, ExclusionReason.NO_ABSTRACT),
        # First failing rule wins.
        (
            {"year": 2000, "abstract": None},
            {"year_from": 2010, "require_abstract": True},
            ExclusionReason.YEAR,
        ),
    ],
)
def test_exclusion_reason(fields, spec, expected):
    assert exclusion_reason(item(**fields), FilterSpec(**spec)) == expected


def test_apply_filters_counts():
    items = [item(year=2010), item(year=2020), item(year=2021, abstract=None)]
    outcome = apply_filters(items, FilterSpec(year_from=2015, require_abstract=True))
    assert outcome.kept == []
    assert outcome.counts() == {ExclusionReason.YEAR: 1, ExclusionReason.NO_ABSTRACT: 2}


def test_invalid_year_range():
    with pytest.raises(ValueError):
        FilterSpec(year_from=2024, year_to=2020)
