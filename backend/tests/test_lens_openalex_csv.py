from bibliomap.parsers import parse_bytes, parse_text
from bibliomap.schema import DocumentType, SourceFormat

# --- Lens -----------------------------------------------------------------


def test_lens_rows_and_untitled_warning(fixture_bytes):
    result = parse_bytes(fixture_bytes("lens_sample.csv"))

    assert result.source_format is SourceFormat.LENS
    assert len(result.records) == 2
    assert [w.record_index for w in result.warnings] == [2]


def test_lens_full_row(fixture_bytes):
    rec = parse_bytes(fixture_bytes("lens_sample.csv")).records[0]

    assert rec.source_id == "000-111-222-333-444"
    assert [a.name for a in rec.authors] == ["Budi Santoso", "Mei-Ling Lee", "Jason R. C. Nurse"]
    assert rec.year == 2021
    assert rec.document_type is DocumentType.ARTICLE
    assert rec.doi == "10.5555/ip-2020-0001"
    # Bare-digit ISSNs are hyphenated; a lower-case check digit is upper-cased.
    assert rec.issn == ["1353-8047", "1475-578X"]
    assert (rec.volume, rec.issue, rec.page_start, rec.page_end) == ("27", "3", "245", "252")
    assert rec.author_keywords == ["motorcycle", "helmet use"]
    assert rec.index_keywords == [
        "Injury prevention",
        "Poison control",
        "Medicine",
        "Humans",
        "Motorcycles",
    ]
    assert rec.cited_by == 10
    assert rec.references == ["000-928-794-577-264", "008-908-495-450-944"]
    assert rec.pmid == "33000001"


def test_lens_conference_article(fixture_bytes):
    rec = parse_bytes(fixture_bytes("lens_sample.csv")).records[1]
    assert rec.document_type is DocumentType.CONFERENCE_PAPER
    assert rec.cited_by == 0
    assert rec.abstract is None


def test_lens_without_id_column_warns():
    result = parse_text("Title,Year\nX,2020\n", SourceFormat.LENS)
    assert result.records == []
    assert "Lens ID" in result.warnings[0].message


# --- OpenAlex CSV ---------------------------------------------------------


def test_openalex_csv_rows(fixture_bytes):
    result = parse_bytes(fixture_bytes("openalex_sample.csv"))

    assert result.source_format is SourceFormat.OPENALEX
    assert len(result.records) == 2
    assert result.warnings == []


def test_openalex_csv_full_row(fixture_bytes):
    rec = parse_bytes(fixture_bytes("openalex_sample.csv")).records[0]

    assert rec.source_id == "W1000000001"
    assert rec.title == "Helmets save lives in Indonesia"
    assert rec.document_type is DocumentType.REVIEW
    assert rec.doi == "10.5555/ip-2020-0001"
    assert rec.pmid == "33000001"
    assert rec.issn == ["1353-8047", "1475-5785"]
    assert rec.cited_by == 12
    assert rec.abstract == "Motorcycle crashes are common."
    # Empty pipe slot keeps ORCIDs aligned with authors.
    assert [(a.name, a.orcid) for a in rec.authors] == [
        ("Budi Santoso", "0000-0002-1825-0097"),
        ("Mei-Ling Lee", None),
    ]
    assert rec.affiliations == ["Universitas Gadjah Mada", "Taipei Medical University"]
    assert rec.index_keywords == ["helmet use", "road safety"]
    assert rec.references == ["W2000000001", "W2000000002"]
    assert (rec.page_start, rec.page_end) == ("245", "252")


def test_openalex_csv_sparse_row(fixture_bytes):
    rec = parse_bytes(fixture_bytes("openalex_sample.csv")).records[1]

    assert rec.year == 2018  # from publication_date
    assert rec.document_type is DocumentType.CONFERENCE_PAPER
    assert rec.issn == ["1742-6588"]  # issn_l fallback
    # ORCID list does not line up with the 3 authors, so none are assigned.
    assert [a.orcid for a in rec.authors] == [None, None, None]
    assert rec.references == []
