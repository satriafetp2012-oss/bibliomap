from bibliomap.parsers import parse_bytes
from bibliomap.schema import DocumentType, SourceFormat


def test_parses_records_and_skips_untitled(fixture_bytes):
    result = parse_bytes(fixture_bytes("wos_sample.txt"))

    assert result.source_format is SourceFormat.WOS
    assert len(result.records) == 2
    assert len(result.warnings) == 1
    assert result.warnings[0].record_index == 2


def test_full_record_fields(fixture_bytes):
    rec = parse_bytes(fixture_bytes("wos_sample.txt")).records[0]

    # Wrapped title lines are joined with a single space.
    assert rec.title == (
        "Road traffic injury among motorcycle riders in Indonesia: a population-based study"
    )
    assert rec.source_id == "WOS:000600000000001"
    assert rec.year == 2021
    assert rec.document_type is DocumentType.ARTICLE
    assert rec.doi == "10.5555/ip-2020-0001"
    assert rec.pmid == "33000001"
    assert rec.issn == ["1353-8047", "1475-5785"]
    assert (rec.volume, rec.issue, rec.page_start, rec.page_end) == ("27", "3", "245", "252")
    assert rec.cited_by == 12
    assert rec.author_keywords == ["motorcycle", "road traffic injury", "helmet use", "Indonesia"]
    assert rec.index_keywords == ["RISK-FACTORS", "HELMET USE", "motorcycle"]
    assert rec.references == [
        "Peden M, 2004, WORLD REPORT ROAD TR",
        "World Health Organization, 2018, GLOBAL STATUS REPORT",
    ]
    assert rec.abstract.startswith("Background Motorcycle") and "Methods We" in rec.abstract


def test_authors_linked_to_affiliations_and_orcid(fixture_bytes):
    authors = parse_bytes(fixture_bytes("wos_sample.txt")).records[0].authors

    assert [a.name for a in authors] == ["Santoso, B", "Lee, ML"]
    assert authors[0].full_name == "Santoso, Budi"
    assert authors[0].orcid == "0000-0002-1825-0097"
    assert authors[0].affiliations == [
        "Univ Gadjah Mada, Fac Med, Dept Biostat, Yogyakarta, Indonesia"
    ]
    assert authors[1].orcid is None
    assert authors[1].affiliations[0].startswith("Taipei Med Univ")


def test_proceedings_without_brackets_or_doi(fixture_bytes):
    rec = parse_bytes(fixture_bytes("wos_sample.txt")).records[1]

    assert rec.document_type is DocumentType.CONFERENCE_PAPER
    assert rec.doi is None
    assert rec.affiliations == ["Univ Indonesia, Depok, Indonesia"]
    assert rec.authors[0].affiliations == []
    assert rec.cited_by == 0


def test_handles_bom_and_missing_trailing_er():
    data = "\ufeffPT J\nAU Doe, J\nTI A truncated record\nPY 2022\n".encode()
    result = parse_bytes(data)

    assert result.source_format is SourceFormat.WOS
    assert [r.title for r in result.records] == ["A truncated record"]
