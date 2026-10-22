"""Format detection and dispatch for bibliographic exports."""

from __future__ import annotations

import re
from collections.abc import Callable

from bibliomap.parsers._common import decode_bytes
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
}

_RIS_LINE = re.compile(r"^[A-Z][A-Z0-9]  - ", re.MULTILINE)
_PUBMED_LINE = re.compile(r"^PMID- ?\d+", re.MULTILINE)
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
    if re.match(r"^TY  - ", head, re.MULTILINE) or len(_RIS_LINE.findall(head)) >= 3:
        return SourceFormat.RIS
    if "Title" in first_line and ("EID" in first_line or "Source title" in first_line):
        return SourceFormat.SCOPUS
    raise UnknownFormatError(
        "Format file tidak dikenali. Gunakan ekspor WoS (plain text), Scopus (CSV), "
        "RIS, atau PubMed (format PubMed/MEDLINE)."
    )


def parse_text(text: str, source_format: SourceFormat | None = None) -> ParseResult:
    """Parse decoded text, auto-detecting the format unless one is given."""
    return _PARSERS[source_format or detect_format(text)](text)


def parse_bytes(data: bytes, source_format: SourceFormat | None = None) -> ParseResult:
    """Parse raw uploaded bytes."""
    return parse_text(decode_bytes(data), source_format)
