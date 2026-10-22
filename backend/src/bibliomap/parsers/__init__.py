"""Format detection and dispatch for bibliographic exports."""

from __future__ import annotations

import csv
import re
from collections.abc import Callable

from bibliomap.parsers._common import decode_bytes
from bibliomap.parsers.bibtex import parse_bibtex
from bibliomap.parsers.lens import parse_lens
from bibliomap.parsers.openalex_csv import is_openalex_csv, parse_openalex_csv
from bibliomap.parsers.pubmed import parse_pubmed
from bibliomap.parsers.ris import parse_ris
from bibliomap.parsers.scopus import parse_scopus
from bibliomap.parsers.wos import parse_wos
from bibliomap.schema import ParseResult, SourceFormat

__all__ = ["UnknownFormatError", "detect_format", "parse_bytes", "parse_text"]

_PARSERS: dict[SourceFormat, Callable[[str], ParseResult]] = {
    SourceFormat.WOS: parse_wos,
    SourceFormat.SCOPUS: parse_scopus,
    SourceFormat.RIS: parse_ris,
    SourceFormat.PUBMED: parse_pubmed,
    SourceFormat.BIBTEX: parse_bibtex,
    SourceFormat.LENS: parse_lens,
    # Files are OpenAlex web CSV exports; API results use bibliomap.openalex.
    SourceFormat.OPENALEX: parse_openalex_csv,
}

_RIS_LINE = re.compile(r"^[A-Z][A-Z0-9]  - ", re.MULTILINE)
_PUBMED_LINE = re.compile(r"^PMID- ?\d+", re.MULTILINE)
_BIBTEX_ENTRY = re.compile(r"^[ \t]*@[A-Za-z]+\s*[{(]", re.MULTILINE)
_WOS_HEADER = re.compile(r"^(FN (Clarivate|Thomson)|PT [JBSP]\s*$)", re.MULTILINE)


class UnknownFormatError(ValueError):
    """Raised when content matches none of the supported formats."""


def detect_format(text: str) -> SourceFormat:
    """Guess the export format from content; filenames are unreliable."""
    head = text.lstrip("\ufeff")[:4000]
    first_line = head.splitlines()[0] if head else ""
    if _WOS_HEADER.search(head):
        return SourceFormat.WOS
    if _PUBMED_LINE.search(head):
        return SourceFormat.PUBMED
    if _BIBTEX_ENTRY.search(head):
        return SourceFormat.BIBTEX
    if re.match(r"^TY  - ", head, re.MULTILINE) or len(_RIS_LINE.findall(head)) >= 3:
        return SourceFormat.RIS

    # CSV exports are told apart by their header row.
    header = next(csv.reader([first_line]), [])
    if "Lens ID" in header:
        return SourceFormat.LENS
    if is_openalex_csv(header):
        return SourceFormat.OPENALEX
    if "Title" in header and ("EID" in header or "Source title" in header):
        return SourceFormat.SCOPUS
    raise UnknownFormatError(
        "Format file tidak dikenali. Gunakan ekspor WoS (plain text), Scopus (CSV), "
        "Lens (CSV), OpenAlex (CSV), BibTeX, RIS, atau PubMed (format PubMed/MEDLINE)."
    )


def parse_text(text: str, source_format: SourceFormat | None = None) -> ParseResult:
    """Parse decoded text, auto-detecting the format unless one is given."""
    return _PARSERS[source_format or detect_format(text)](text)


def parse_bytes(data: bytes, source_format: SourceFormat | None = None) -> ParseResult:
    """Parse raw uploaded bytes."""
    return parse_text(decode_bytes(data), source_format)
