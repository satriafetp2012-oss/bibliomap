import pytest

from bibliomap.parsers import parse_bytes
from bibliomap.schema import DocumentType, SourceFormat


def test_parses_records_and_skips_untitled(fixture_bytes):
    result = parse_bytes(fixture_bytes("ris_sample.ris"))

    assert result.source_format is SourceFormat.RIS
    assert len(result.records) == 2
    assert [w.record_index for w in result.warnings] == [2]


def test_journal_record(fixture_bytes):
    rec = parse_bytes(fixture_bytes("ris_sample.ris")).records[0]

    assert [a.name for a in rec.authors] == ["Santoso, Budi", "Lee, Mei-Ling"]
    assert rec.year == 2021
    assert rec.source_title == "Injury Prevention"
    assert rec.source_abbrev == "Inj Prev"
    assert rec.document_type is DocumentType.ARTICLE
    assert rec.doi == "10.5555/ip-2020-0001"
    # Duplicate keywords are removed, order kept.
    assert rec.author_keywords == ["motorcycle", "helmet use"]
    # Untagged continuation line is appended to the abstract.
    assert rec.abstract.endswith("in low- and middle-income countries.")
    assert rec.source_id == "2-s2.0-85000000001"
    assert rec.affiliations == ["Universitas Gadjah Mada, Yogyakarta, Indonesia"]


def test_conference_record_uses_alternate_tags(fixture_bytes):
    rec = parse_bytes(fixture_bytes("ris_sample.ris")).records[1]

    assert rec.title == "Helmet law enforcement and fatality trends"
    assert [a.name for a in rec.authors] == ["Rahman, Arif"]
    assert rec.year == 2019
    assert rec.source_title == "Proceedings of the Asian Conference on Safety"
    assert rec.document_type is DocumentType.CONFERENCE_PAPER
    # DOI recovered from the UR field.
    assert rec.doi == "10.5555/acs.2019.12"


# Patterns observed in real Scopus, WoS, EMBASE and ScienceDirect RIS exports
# (fixture is synthetic, with CRLF line endings).


@pytest.fixture
def variants(fixture_bytes):
    return parse_bytes(fixture_bytes("ris_vendor_variants.ris"))


def test_vendor_variants_all_parse(variants):
    assert len(variants.records) == 4
    assert variants.warnings == []


def test_scopus_m3_note_and_article_number(variants):
    rec = variants.records[0]
    assert rec.document_type is DocumentType.REVIEW
    assert rec.document_type_raw == "Review"
    assert rec.cited_by == 4
    assert rec.article_number == "105507"
    assert rec.source_abbrev == "Inj. Prev."


def test_wos_cited_references_and_times_cited(variants):
    rec = variants.records[1]
    assert rec.cited_by == 10  # Core Collection count, not total
    assert len(rec.references) == 2
    assert rec.references[1].endswith("DOI 10.1056/NEJMoa041365")
    assert rec.source_abbrev == "INJURY PREV"
    assert rec.publisher == "BMJ PUBLISHING GROUP"
    assert rec.source_id == "WOS:000600000000001"


def test_embase_title_in_t2_and_journal_in_jf(variants):
    rec = variants.records[2]
    assert rec.title == "Criterios de retorno al trabajo por Covid-19"
    assert rec.source_title == "Salud Publica de Mexico"
    assert rec.document_type is DocumentType.LETTER


def test_sciencedirect_book_with_only_bt(variants):
    rec = variants.records[3]
    assert rec.title == "Global HIV/AIDS Medicine"
    assert rec.source_title is None
    assert rec.document_type is DocumentType.BOOK
    assert rec.doi == "10.5555/b978-1-4160-2882-6.x5001-x"
