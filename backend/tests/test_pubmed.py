from bibliomap.parsers import parse_bytes
from bibliomap.schema import DocumentType, SourceFormat


def test_parses_records(fixture_bytes):
    result = parse_bytes(fixture_bytes("pubmed_sample.nbib"))

    assert result.source_format is SourceFormat.PUBMED
    assert len(result.records) == 2
    assert result.warnings == []


def test_full_record_fields(fixture_bytes):
    rec = parse_bytes(fixture_bytes("pubmed_sample.nbib")).records[0]

    # Wrapped lines joined; trailing MEDLINE period removed.
    assert rec.title == (
        "Road traffic injury among motorcycle riders in Indonesia: a population-based study"
    )
    assert rec.pmid == rec.source_id == "33000001"
    assert rec.year == 2021
    assert rec.doi == "10.5555/ip-2020-0001"
    # Abbreviated end page "52" expands to "252".
    assert (rec.page_start, rec.page_end) == ("245", "252")
    assert rec.issn == ["1475-5785", "1353-8047"]
    assert rec.source_abbrev == "Inj Prev"
    assert rec.source_title.endswith("Adolescent Injury Prevention")
    # Review outranks Journal Article.
    assert rec.document_type is DocumentType.REVIEW
    assert rec.document_type_raw == "Journal Article; Review"
    assert rec.index_keywords == ["Accidents, Traffic", "Humans", "Motorcycles"]
    assert rec.author_keywords == ["helmet use", "Indonesia"]
    assert "METHODS: We analysed" in rec.abstract


def test_affiliations_and_orcid_attach_to_preceding_author(fixture_bytes):
    authors = parse_bytes(fixture_bytes("pubmed_sample.nbib")).records[0].authors

    assert [(a.name, a.full_name) for a in authors] == [
        ("Santoso B", "Santoso, Budi"),
        ("Lee ML", "Lee, Mei-Ling"),
    ]
    assert authors[0].orcid == "0000-0002-1825-0097"
    assert len(authors[0].affiliations) == 1
    assert len(authors[1].affiliations) == 2
    assert authors[1].orcid is None


def test_minimal_record_without_fau(fixture_bytes):
    rec = parse_bytes(fixture_bytes("pubmed_sample.nbib")).records[1]

    assert [a.name for a in rec.authors] == ["Rahman A"]
    assert rec.authors[0].full_name is None
    assert rec.document_type is DocumentType.LETTER
    assert (rec.page_start, rec.page_end) == ("e12", None)
    assert rec.doi is None
