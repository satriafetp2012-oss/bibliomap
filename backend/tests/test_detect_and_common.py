import pytest

from bibliomap.parsers import UnknownFormatError, detect_format
from bibliomap.parsers._common import (
    decode_bytes,
    expand_page_range,
    map_document_type,
    normalize_doi,
    parse_year,
)
from bibliomap.schema import DocumentType, SourceFormat


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("wos_sample.txt", SourceFormat.WOS),
        ("scopus_sample.csv", SourceFormat.SCOPUS),
        ("ris_sample.ris", SourceFormat.RIS),
        ("pubmed_sample.nbib", SourceFormat.PUBMED),
        ("bibtex_sample.bib", SourceFormat.BIBTEX),
    ],
)
def test_detects_each_fixture(fixture_bytes, name, expected):
    assert detect_format(decode_bytes(fixture_bytes(name))) is expected


def test_unknown_format_raises():
    with pytest.raises(UnknownFormatError):
        detect_format("hello world\nthis is not a bibliography\n")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10.1000/ABC", "10.1000/abc"),
        ("https://doi.org/10.1000/abc.", "10.1000/abc"),
        ("http://dx.doi.org/10.1000/abc", "10.1000/abc"),
        ("doi: 10.1000/abc", "10.1000/abc"),
        ("not a doi", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_doi(raw, expected):
    assert normalize_doi(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("2021 Jun", 2021), ("2020/05/01/", 2020), ("c1998", 1998), ("n.d.", None), (None, None)],
)
def test_parse_year(raw, expected):
    assert parse_year(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("245-52", ("245", "252")),
        ("1001-9", ("1001", "1009")),
        ("12-130", ("12", "130")),
        ("e12", ("e12", None)),
        ("S1-S9", ("S1", "S9")),
        (None, (None, None)),
    ],
)
def test_expand_page_range(raw, expected):
    assert expand_page_range(raw) == expected


def test_map_document_type_priority_and_unknown():
    assert map_document_type("Journal Article", "Review") is DocumentType.REVIEW
    assert map_document_type("Something new") is DocumentType.OTHER
    assert map_document_type(None) is DocumentType.OTHER


def test_decode_bytes_encodings():
    assert decode_bytes("\ufeffTitle".encode()) == "Title"
    assert decode_bytes("Título".encode("utf-16")) == "Título"
    assert decode_bytes("Caf\xe9".encode("cp1252")) == "Café"
