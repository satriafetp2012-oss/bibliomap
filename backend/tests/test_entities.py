import pytest

from bibliomap.analysis.entities import (
    EntityKind,
    Thesaurus,
    author_key,
    build_index,
    country_from_affiliation,
    document_label,
    extract,
    organization_from_affiliation,
)
from bibliomap.schema import Author, Record, SourceFormat


def rec(**fields) -> Record:
    fields.setdefault("title", "T")
    return Record(source_format=SourceFormat.WOS, **fields)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Santoso, Budi", "santoso b"),
        ("Santoso B", "santoso b"),
        ("Santoso BS", "santoso bs"),
        ("Budi Santoso", "santoso b"),
        ("SANTOSO, B.", "santoso b"),
        ("Müller, Jörg", "muller j"),
        ("van der Berg, Jan", "van der berg j"),
        ("Nurse, Jason R. C.", "nurse jrc"),
        ("Jason R. C. Nurse", "nurse jrc"),
        # Two different people keep their own keys.
        ("da Silva DH", "da silva dh"),
        ("da Silva DA", "da silva da"),
        ("Cher", "cher"),
        ("World Health Organization", "organization wh"),
        ("Lee, Mei-Ling (12345)", "lee ml"),
        ("", None),
        (",", None),
    ],
)
def test_author_key(name, expected):
    assert author_key(name) == expected


@pytest.mark.parametrize(
    ("affiliation", "expected"),
    [
        ("Univ Gadjah Mada, Fac Med, Yogyakarta, Indonesia", "Indonesia"),
        ("Harvard Med Sch, Boston, MA 02115 USA", "United States"),
        ("Univ Oxford, Oxford, England", "United Kingdom"),
        ("Peking Univ, Beijing, Peoples R China", "China"),
        ("Seoul Natl Univ, Seoul, Republic of Korea", "South Korea"),
        ("Natl Taiwan Univ, Taipei, Taiwan ROC", "Taiwan"),
        ("Columbia Univ, New York, NY 10032 USA", "United States"),
        # A city or state alone is not a country.
        ("Universitas Indonesia, Depok", None),
        ("Some Lab, Nowhere", None),
        ("", None),
    ],
)
def test_country_from_affiliation(affiliation, expected):
    assert country_from_affiliation(affiliation) == expected


@pytest.mark.parametrize(
    ("affiliation", "expected"),
    [
        ("Univ Gadjah Mada, Fac Med, Dept Biostat, Yogyakarta, Indonesia", "Univ Gadjah Mada"),
        ("Dept of Epidemiology, Harvard Med Sch, Boston, USA", "Harvard Med Sch"),
        ("Some Place, Nowhere", "Some Place"),
    ],
)
def test_organization_from_affiliation(affiliation, expected):
    assert organization_from_affiliation(affiliation) == expected


def test_extract_authors_deduplicates_and_prefers_longest_label():
    record = rec(
        authors=[Author(name="Santoso, B", full_name="Santoso, Budi"), Author(name="Santoso B")]
    )
    mentions = extract(record, EntityKind.AUTHOR)
    assert [(m.key, m.label) for m in mentions] == [("santoso b", "Santoso, Budi")]


def test_extract_country_from_author_affiliations_when_record_has_none():
    record = rec(
        authors=[
            Author(name="A", affiliations=["Univ X, Yogyakarta, Indonesia"]),
            Author(name="B", affiliations=["Univ Y, Taipei, Taiwan"]),
        ]
    )
    assert sorted(m.label for m in extract(record, EntityKind.COUNTRY)) == ["Indonesia", "Taiwan"]


def test_thesaurus_merges_and_drops():
    th = Thesaurus.from_pairs(
        replace={"covid 19": "COVID-19", "sars cov 2": "COVID-19"}, drop={"study", "humans"}
    )
    record = rec(author_keywords=["COVID-19", "SARS-CoV-2", "study", "helmet"])
    labels = sorted(m.label for m in extract(record, EntityKind.KEYWORD, th))
    assert labels == ["COVID-19", "helmet"]


def test_document_label():
    assert document_label(
        rec(authors=[Author(name="Santoso, B")], year=2021, source_abbrev="Inj Prev")
    ) == ("Santoso B, 2021, Inj Prev")
    assert document_label(rec()) == "Anon, n.d."


def test_build_index_counts_documents():
    records = {
        1: rec(authors=[Author(name="Santoso, Budi"), Author(name="Lee, ML")]),  # Lee ML
        2: rec(authors=[Author(name="Santoso B")]),
        3: rec(authors=[Author(name="Wijaya, A")]),
    }
    index = build_index(records, EntityKind.AUTHOR)

    assert index.labels["santoso b"] == "Santoso, Budi"
    assert index.documents["santoso b"] == [1, 2]
    assert index.occurrences("santoso b") == 2
    assert index.top(2) == [("santoso b", 2), ("lee ml", 1)]
    assert index.by_document[1] == ["santoso b", "lee ml"]
