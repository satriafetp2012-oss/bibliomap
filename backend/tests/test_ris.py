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
