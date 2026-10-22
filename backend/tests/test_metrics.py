import pytest

from bibliomap.analysis.entities import EntityKind
from bibliomap.analysis.metrics import (
    annual_growth_rate,
    bradford,
    g_index,
    h_index,
    lotka,
    m_index,
    overview,
    rank_entities,
)
from bibliomap.schema import Author, DocumentType, Record, SourceFormat


def rec(**fields) -> Record:
    fields.setdefault("title", "T")
    return Record(source_format=SourceFormat.WOS, **fields)


# --- index metrics (published worked examples) ----------------------------


@pytest.mark.parametrize(
    ("citations", "expected"),
    [
        ([], 0),
        ([0, 0, 0], 0),
        ([10, 8, 5, 4, 3], 4),
        ([25, 8, 5, 3, 3], 3),
        ([5, 5, 5, 5, 5], 5),
        ([100], 1),
    ],
)
def test_h_index(citations, expected):
    assert h_index(citations) == expected


@pytest.mark.parametrize(
    ("citations", "expected"),
    [
        ([], 0),
        # Egghe's example: h = 4 but the top papers carry far more citations.
        ([10, 8, 5, 4, 3], 5),
        ([25, 8, 5, 3, 3], 5),
        ([1, 1, 1], 1),
    ],
)
def test_g_index(citations, expected):
    assert g_index(citations) == expected


def test_g_index_is_at_least_h_index():
    citations = [12, 9, 7, 3, 2, 1]
    assert g_index(citations) >= h_index(citations)


def test_m_index():
    assert m_index(10, 2016, 2025) == 1.0
    assert m_index(5, 2021, 2025) == 1.0
    assert m_index(3, None, 2025) is None


def test_annual_growth_rate():
    from bibliomap.analysis.metrics import YearCount

    # 10 -> 40 over two years doubles each year.
    years = [YearCount(year=2020, count=10), YearCount(year=2022, count=40)]
    assert annual_growth_rate(years) == 100.0
    assert annual_growth_rate(years[:1]) is None


# --- overview -------------------------------------------------------------


@pytest.fixture
def corpus() -> dict[int, Record]:
    return {
        1: rec(
            year=2020,
            cited_by=10,
            source_title="Injury Prevention",
            authors=[
                Author(
                    name="Santoso, Budi", affiliations=["Univ Gadjah Mada, Yogyakarta, Indonesia"]
                ),
                Author(name="Lee, ML", affiliations=["Taipei Med Univ, Taipei, Taiwan"]),
            ],
            author_keywords=["helmet", "motorcycle"],
            references=["Ref A", "Ref B"],
        ),
        2: rec(
            year=2021,
            cited_by=4,
            source_title="Injury Prevention",
            authors=[
                Author(name="Santoso B", affiliations=["Univ Gadjah Mada, Yogyakarta, Indonesia"])
            ],
            author_keywords=["helmet"],
            document_type=DocumentType.REVIEW,
        ),
        3: rec(
            year=2021,
            cited_by=0,
            source_title="Safety Science",
            authors=[Author(name="Wijaya, A"), Author(name="Santoso, B")],
        ),
    }


def test_overview(corpus):
    o = overview(corpus)

    assert o.documents == 3
    assert o.sources == 2
    # Santoso's three spellings collapse into one author.
    assert o.authors == 3
    assert o.single_authored == 1
    assert (o.year_min, o.year_max) == (2020, 2021)
    assert o.total_citations == 14
    assert o.mean_citations == pytest.approx(4.67, abs=0.01)
    assert o.mean_authors_per_document == pytest.approx(1.67, abs=0.01)
    assert o.collaboration_index == 2.0
    # Only document 1 has authors from two countries; 2 has one country.
    assert o.international_coauthorship_pct == 50.0
    assert [y.model_dump() for y in o.documents_per_year] == [
        {"year": 2020, "count": 1, "mean_citations": 10.0},
        {"year": 2021, "count": 2, "mean_citations": 2.0},
    ]
    # rec() leaves document_type at its default.
    assert o.document_types == {"other": 2, "review": 1}
    assert o.references == 2


def test_overview_of_empty_corpus():
    o = overview({})
    assert o.documents == 0 and o.mean_citations == 0.0 and o.year_min is None


def test_rank_entities(corpus):
    authors = rank_entities(corpus, EntityKind.AUTHOR, current_year=2021)
    top = authors[0]

    assert top.label == "Santoso, Budi"
    assert top.documents == 3
    assert top.citations == 14
    assert top.h_index == 2
    assert top.first_year == 2020
    assert top.m_index == 1.0

    sources = rank_entities(corpus, EntityKind.SOURCE)
    assert (sources[0].label, sources[0].documents) == ("Injury Prevention", 2)

    countries = rank_entities(corpus, EntityKind.COUNTRY)
    assert {c.label for c in countries} == {"Indonesia", "Taiwan"}


# --- Lotka ----------------------------------------------------------------


def test_lotka_on_inverse_square_distribution():
    # Build authors so counts follow 1/n^2 exactly: 100, 25, 11, 6 authors.
    records: dict[int, Record] = {}
    doc_id = 0
    author_id = 0
    for n, author_count in [(1, 100), (2, 25), (3, 11), (4, 6)]:
        for _ in range(author_count):
            author_id += 1
            for _ in range(n):
                doc_id += 1
                records[doc_id] = rec(authors=[Author(name=f"Person{author_id}, A")])

    fit = lotka(records)

    assert [r.documents_written for r in fit.rows] == [1, 2, 3, 4]
    assert [r.authors for r in fit.rows] == [100, 25, 11, 6]
    assert fit.exponent == pytest.approx(2.0, abs=0.1)
    assert fit.r_squared > 0.99
    assert fit.ks_statistic < 0.05
    assert sum(r.proportion for r in fit.rows) == pytest.approx(1.0, abs=0.01)
    assert sum(r.fitted_proportion for r in fit.rows) == pytest.approx(1.0, abs=0.01)


def test_lotka_empty():
    assert lotka({}).rows == []


# --- Bradford -------------------------------------------------------------


def test_bradford_zones_split_documents_evenly():
    records: dict[int, Record] = {}
    doc_id = 0
    # 1 source with 30 docs, 3 with 10, 30 with 1: 90 documents total.
    for source, count in [("Core A", 30), ("B", 10), ("C", 10), ("D", 10)]:
        for _ in range(count):
            doc_id += 1
            records[doc_id] = rec(source_title=source)
    for i in range(30):
        doc_id += 1
        records[doc_id] = rec(source_title=f"Tail {i}")

    analysis = bradford(records)

    assert analysis.rows[0].label == "Core A"
    assert analysis.rows[0].zone == 1
    assert sum(analysis.zone_documents) == 90
    assert analysis.zone_sources[0] < analysis.zone_sources[-1]
    assert analysis.rows[-1].cumulative == 90
    assert analysis.multiplier is not None and analysis.multiplier > 1


def test_bradford_empty():
    assert bradford({}).rows == []
