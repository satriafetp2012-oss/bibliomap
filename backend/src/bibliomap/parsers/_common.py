"""Helpers shared by all format parsers."""

from __future__ import annotations

import re

from bibliomap.schema import DocumentType

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_YEAR = re.compile(r"(?<!\d)(1[5-9]\d{2}|2\d{3})(?!\d)")
_WS = re.compile(r"\s+")

# Lower-cased raw type label -> normalized type. Covers WoS DT, Scopus
# "Document Type", RIS TY and PubMed PT vocabularies.
_DOCTYPE_MAP: dict[str, DocumentType] = {
    # WoS / Scopus
    "article": DocumentType.ARTICLE,
    "review": DocumentType.REVIEW,
    "proceedings paper": DocumentType.CONFERENCE_PAPER,
    "conference paper": DocumentType.CONFERENCE_PAPER,
    "conference review": DocumentType.CONFERENCE_PAPER,
    "book": DocumentType.BOOK,
    "book chapter": DocumentType.BOOK_CHAPTER,
    "editorial": DocumentType.EDITORIAL,
    "editorial material": DocumentType.EDITORIAL,
    "letter": DocumentType.LETTER,
    # RIS TY codes
    "jour": DocumentType.ARTICLE,
    "ejour": DocumentType.ARTICLE,
    "conf": DocumentType.CONFERENCE_PAPER,
    "cpaper": DocumentType.CONFERENCE_PAPER,
    "chap": DocumentType.BOOK_CHAPTER,
    "echap": DocumentType.BOOK_CHAPTER,
    "ebook": DocumentType.BOOK,
    # PubMed PT
    "journal article": DocumentType.ARTICLE,
    "systematic review": DocumentType.REVIEW,
    "meta-analysis": DocumentType.REVIEW,
    "comment": DocumentType.LETTER,
}

# When a record carries several PubMed PT values, the most specific wins.
_DOCTYPE_PRIORITY = [
    DocumentType.REVIEW,
    DocumentType.EDITORIAL,
    DocumentType.LETTER,
    DocumentType.CONFERENCE_PAPER,
    DocumentType.BOOK_CHAPTER,
    DocumentType.BOOK,
    DocumentType.ARTICLE,
]


def decode_bytes(data: bytes) -> str:
    """Decode an uploaded export, tolerating BOMs and legacy encodings."""
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        # utf-16 without a BOM happily decodes ASCII into garbage; require a BOM.
        if encoding == "utf-16" and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
            continue
        return text
    return data.decode("cp1252", errors="replace")


def clean(value: str | None) -> str | None:
    """Collapse whitespace; map empty strings to ``None``."""
    if value is None:
        return None
    value = _WS.sub(" ", value).strip()
    return value or None


def normalize_doi(value: str | None) -> str | None:
    """Return a bare, lower-case DOI such as ``10.1000/xyz``."""
    value = clean(value)
    if not value:
        return None
    value = _DOI_PREFIX.sub("", value).rstrip(".,; ")
    return value.lower() if value.startswith("10.") else None


def parse_year(value: str | None) -> int | None:
    """Extract the first plausible four-digit year."""
    if not value:
        return None
    match = _YEAR.search(value)
    return int(match.group(1)) if match else None


def parse_int(value: str | None) -> int | None:
    value = clean(value)
    if value is None:
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError:
        return None


def split_list(value: str | None, sep: str = ";") -> list[str]:
    """Split a delimited field, trimming items and dropping empties."""
    if not value:
        return []
    items = (clean(part) for part in value.split(sep))
    return [item for item in items if item]


def dedupe(items: list[str]) -> list[str]:
    """Remove duplicates while keeping first-seen order."""
    return list(dict.fromkeys(items))


def map_document_type(*raw_values: str | None) -> DocumentType:
    """Map one or more raw type labels to the most specific normalized type."""
    found = {
        _DOCTYPE_MAP[key]
        for raw in raw_values
        if raw and (key := raw.strip().lower()) in _DOCTYPE_MAP
    }
    for doc_type in _DOCTYPE_PRIORITY:
        if doc_type in found:
            return doc_type
    return DocumentType.OTHER


def expand_page_range(value: str | None) -> tuple[str | None, str | None]:
    """Split '123-45' into ('123', '145'); MEDLINE abbreviates the end page."""
    value = clean(value)
    if not value:
        return None, None
    start, _, end = value.partition("-")
    start, end = start.strip(), end.strip()
    if not end:
        return start or None, None
    if start.isdigit() and end.isdigit() and len(end) < len(start):
        end = start[: len(start) - len(end)] + end
    return start or None, end or None
