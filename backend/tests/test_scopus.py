from bibliomap.parsers import parse_bytes, parse_text
from bibliomap.schema import DocumentType, SourceFormat


def test_parses_rows_and_skips_untitled(fixture_bytes):
    result = parse_bytes(fixture_bytes("scopus_sample.csv"))

    assert result.source_format is SourceFormat.SCOPUS
    assert len(result.records) == 2
    assert [w.record_index for w in result.warnings] == [2]


def test_full_row_fields(fixture_bytes):
    rec = parse_bytes(fixture_bytes("scopus_sample.csv")).records[0]

    assert rec.source_id == "2-s2.0-85000000001"
    assert rec.year == 2021
    assert rec.document_type is DocumentType.ARTICLE
    assert rec.doi == "10.5555/ip-2020-0001"
    assert rec.issn == ["1353-8047"]
    assert rec.cited_by == 15
    assert rec.pmid == "33000001"
    assert "São Paulo" in rec.abstract
    assert rec.author_keywords == ["motorcycle", "helmet use", "Indonesia"]
    assert rec.index_keywords == ["adult", "human", "motorcycle"]
    assert len(rec.references) == 2
    assert rec.affiliations == [
        "Universitas Gadjah Mada, Yogyakarta, Indonesia",
        "Taipei Medical University, Taipei, Taiwan",
    ]


def test_new_author_format_with_full_names_and_affiliations(fixture_bytes):
    authors = parse_bytes(fixture_bytes("scopus_sample.csv")).records[0].authors

    assert [a.name for a in authors] == ["Santoso B.", "Lee M.-L."]
    # Scopus author IDs in parentheses are stripped from full names.
    assert [a.full_name for a in authors] == ["Santoso, Budi", "Lee, Mei-Ling"]
    assert authors[0].affiliations == ["Universitas Gadjah Mada, Yogyakarta, Indonesia"]
    assert authors[1].affiliations == ["Taipei Medical University, Taipei, Taiwan"]


def test_old_author_format_and_placeholders(fixture_bytes):
    rec = parse_bytes(fixture_bytes("scopus_sample.csv")).records[1]

    assert [a.name for a in rec.authors] == ["Rahman A.", "Putri S.D."]
    assert rec.abstract is None
    assert rec.doi is None
    assert rec.cited_by is None
    assert rec.article_number == "e12"
    assert rec.document_type is DocumentType.CONFERENCE_PAPER


def test_csv_without_title_column_warns():
    result = parse_text("Foo,Bar\n1,2\n", SourceFormat.SCOPUS)

    assert result.records == []
    assert "Title" in result.warnings[0].message
