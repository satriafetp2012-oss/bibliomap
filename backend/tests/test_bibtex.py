import pytest

from bibliomap.parsers import parse_bytes, parse_text
from bibliomap.parsers.bibtex import latex_to_text
from bibliomap.schema import DocumentType, SourceFormat


@pytest.fixture
def result(fixture_bytes):
    return parse_bytes(fixture_bytes("bibtex_sample.bib"))


def test_counts_and_warnings(result):
    assert result.source_format is SourceFormat.BIBTEX
    assert [r.title for r in result.records][-1] == "A record after the broken one"
    assert len(result.records) == 4
    messages = [w.message for w in result.warnings]
    assert any("rusak" in m for m in messages)
    assert any("untitled2022" in m for m in messages)


def test_wos_flavour(result):
    rec = result.records[0]

    assert rec.title == (
        "Road traffic injury among motorcycle riders in Indonesia: a population-based study"
    )
    assert rec.source_title == "Injury Prevention"  # resolved from @string
    assert rec.source_id == "WOS:000600000000001"
    assert rec.year == 2021
    assert rec.document_type is DocumentType.ARTICLE
    assert rec.doi == "10.5555/ip-2020-0001"
    assert rec.issn == ["1353-8047", "1475-5785"]
    assert (rec.page_start, rec.page_end) == ("245", "252")
    assert rec.cited_by == 12
    assert rec.author_keywords == ["motorcycle", "road traffic injury", "helmet use"]
    assert rec.index_keywords == ["RISK-FACTORS", "HELMET USE"]
    assert len(rec.affiliations) == 2
    assert rec.references == [
        "Peden M, 2004, WORLD REPORT ROAD TR.",
        "World Health Organization, 2018, GLOBAL STATUS REPORT.",
    ]
    assert [a.name for a in rec.authors] == ["Santoso, Budi", "Lee, Mei-Ling"]
    assert rec.authors[0].orcid == "0000-0002-1825-0097"


def test_scopus_flavour(result):
    rec = result.records[1]

    assert rec.source_id == "2-s2.0-85000000002"
    assert rec.document_type is DocumentType.CONFERENCE_PAPER
    assert rec.cited_by == 3
    # In Scopus BibTeX, `keywords` are index keywords.
    assert rec.author_keywords == ["helmet", "law enforcement"]
    assert rec.index_keywords == ["human", "safety"]
    assert rec.affiliations == [
        "Universitas Indonesia, Depok, Indonesia",
        "Universitas Airlangga, Surabaya, Indonesia",
    ]
    assert len(rec.references) == 2
    assert (rec.page_start, rec.page_end) == ("1", "9")
    assert rec.source_abbrev == "Proc. Asian Conf. Saf."


def test_reference_manager_flavour_with_latex(result):
    rec = result.records[2]

    assert rec.title == "Verkehrssicherheit in Südostasien: Étude comparative"
    assert [a.name for a in rec.authors] == [
        "Müller, Jörg",
        "García, Ana",
        "World Health Organization",
    ]
    assert rec.source_title == "Road Safety & Public Health"
    assert rec.year == 2020
    assert rec.document_type is DocumentType.BOOK_CHAPTER
    assert rec.doi == "10.5555/book.2020.3"
    assert (rec.page_start, rec.page_end) == ("12", "30")
    assert rec.author_keywords == ["road safety", "Southeast Asia"]


def test_bare_number_and_parenthesised_entry():
    text = "@misc(x, title = {Paren entry}, year = 1999)"
    rec = parse_text(text).records[0]
    assert (rec.title, rec.year) == ("Paren entry", 1999)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (r"S{\"u}d", "Süd"),
        (r"\'Etude", "Étude"),
        (r"Garc{\'\i}a", "García"),
        (r"{\v{S}}koda", "Škoda"),
        (r"Stra{\ss}e", "Straße"),
        (r"A \& B, 50\%", "A & B, 50%"),
        ("pages 1--9", "pages 1\u20139"),
        ("{NASA} rocks", "NASA rocks"),
    ],
)
def test_latex_to_text(raw, expected):
    assert latex_to_text(raw) == expected
