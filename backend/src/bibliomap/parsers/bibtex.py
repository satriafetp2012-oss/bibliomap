"""BibTeX parser covering WoS, Scopus and reference-manager exports.

The tokenizer is a small hand-written scanner rather than a regex because
BibTeX values nest braces, concatenate with ``#`` and reference ``@string``
macros. Field semantics differ by exporter (e.g. ``keywords`` means author
keywords in WoS but index keywords in Scopus), so the source is detected per
entry.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from bibliomap.parsers._common import (
    clean,
    dedupe,
    map_document_type,
    normalize_doi,
    parse_int,
    parse_year,
    split_list,
)
from bibliomap.schema import Author, ParseResult, ParseWarning, Record, SourceFormat

_MONTHS = {
    m: m.capitalize()
    for m in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
}
_SKIP_TYPES = {"comment", "preamble"}
_ENTRY_START = re.compile(r"@\s*([A-Za-z]+)\s*([{(])")
_LINE_ENTRY_START = re.compile(r"^[ \t]*@\s*[A-Za-z]+\s*[{(]", re.MULTILINE)

# LaTeX accent command -> Unicode combining mark.
_ACCENTS = {
    "'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303",
    "=": "\u0304", ".": "\u0307", "u": "\u0306", "v": "\u030c", "H": "\u030b",
    "c": "\u0327", "k": "\u0328",
}  # fmt: skip
_SYMBOL_ACCENT = re.compile(r"\\([\'`^\"~=.])\s*(?:\{\s*([A-Za-z])\s*\}|([A-Za-z]))")
_LETTER_ACCENT = re.compile(r"\\([uvHck])\s*(?:\{\s*([A-Za-z])\s*\}|\s([A-Za-z]))")
_SPECIAL_LETTERS = {
    r"\ss": "ß", r"\ae": "æ", r"\AE": "Æ", r"\oe": "œ", r"\OE": "Œ", r"\aa": "å",
    r"\AA": "Å", r"\o": "ø", r"\O": "Ø", r"\l": "ł", r"\L": "Ł", r"\i": "\u0131",
}  # fmt: skip
_SPECIAL_LETTER = re.compile(r"\\(ss|ae|AE|oe|OE|aa|AA|o|O|l|L|i)(?![A-Za-z])\s?")
# An accent over dotless \i or \j (e.g. {\'\i}) means a plain accented i/j.
_ACCENTED_DOTLESS = re.compile(r"(\\[\'`^\"~=.uvHck])\s*\{?\\([ij])(?![A-Za-z])\}?")
_ESCAPED_CHAR = re.compile(r"\\([&%$#_{}])")
_AND = re.compile(r"\s+and\s+", re.IGNORECASE)
_ORCID_ENTRY = re.compile(r"^(?P<name>.+?)/(?P<id>\d{4}-\d{4}-\d{4}-\d{3}[\dX])$")
_SCOPUS_EID = re.compile(r"eid=(2-s2\.0-\d+)")
_CITED_BY = re.compile(r"Cited by:\s*(\d+)", re.IGNORECASE)


class BibtexSyntaxError(ValueError):
    pass


@dataclass
class _Entry:
    entry_type: str
    key: str
    fields: dict[str, str] = field(default_factory=dict)


class _Scanner:
    """Character scanner over the whole file."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.macros: dict[str, str] = dict(_MONTHS)
        self.entry_start = 0

    def _peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def _expect(self, chars: str) -> str:
        self._skip_ws()
        char = self._peek()
        if not char or char not in chars:
            raise BibtexSyntaxError(f"'{chars}' diharapkan pada posisi {self.pos}")
        self.pos += 1
        return char

    def _read_name(self) -> str:
        self._skip_ws()
        start = self.pos
        while self.pos < len(self.text) and (
            self.text[self.pos].isalnum() or self.text[self.pos] in "_-:.+/"
        ):
            self.pos += 1
        if start == self.pos:
            raise BibtexSyntaxError(f"Nama field diharapkan pada posisi {self.pos}")
        return self.text[start : self.pos]

    def _read_braced(self) -> str:
        """Read a {...} group (opening brace already consumed), keeping inner braces."""
        depth, start = 1, self.pos
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\":
                self.pos += 2
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    value = self.text[start : self.pos]
                    self.pos += 1
                    return value
            self.pos += 1
        raise BibtexSyntaxError("Kurung kurawal tidak tertutup")

    def _read_quoted(self) -> str:
        """Read a "..." string; quotes inside braces do not terminate it."""
        depth, start = 0, self.pos
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == "\\":
                self.pos += 2
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            elif char == '"' and depth == 0:
                value = self.text[start : self.pos]
                self.pos += 1
                return value
            self.pos += 1
        raise BibtexSyntaxError("Tanda kutip tidak tertutup")

    def _read_value(self) -> str:
        """Read one value, resolving '#' concatenation and macros."""
        parts: list[str] = []
        while True:
            self._skip_ws()
            char = self._peek()
            if char == "{":
                self.pos += 1
                parts.append(self._read_braced())
            elif char == '"':
                self.pos += 1
                parts.append(self._read_quoted())
            else:
                name = self._read_name()
                parts.append(name if name.isdigit() else self.macros.get(name.lower(), name))
            self._skip_ws()
            if self._peek() != "#":
                return "".join(parts)
            self.pos += 1

    def _read_fields(self, closer: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        while True:
            self._skip_ws()
            if self._peek() == closer:
                self.pos += 1
                return fields
            if self._peek() == ",":
                self.pos += 1
                continue
            name = self._read_name().lower()
            self._expect("=")
            fields[name] = self._read_value()

    def next_entry(self) -> _Entry | None:
        """Return the next data entry, or None at end of input."""
        while True:
            # Only '@type{' starts an entry; a bare '@' (e.g. in an email) is text.
            match = _ENTRY_START.search(self.text, self.pos)
            if match is None:
                return None
            self.entry_start = match.start()
            self.pos = match.end()
            entry_type = match.group(1).lower()
            closer = "}" if match.group(2) == "{" else ")"

            if entry_type in _SKIP_TYPES:
                if closer == "}":
                    self._read_braced()
                else:
                    self._skip_to(closer)
                continue
            if entry_type == "string":
                self.macros.update(self._read_fields(closer))
                continue

            self._skip_ws()
            key_end = self.text.find(",", self.pos)
            if key_end < 0:
                raise BibtexSyntaxError("Kunci entri tanpa koma")
            key = self.text[self.pos : key_end].strip()
            self.pos = key_end + 1
            return _Entry(entry_type, key, self._read_fields(closer))

    def _skip_to(self, char: str) -> None:
        end = self.text.find(char, self.pos)
        self.pos = len(self.text) if end < 0 else end + 1

    def recover(self) -> None:
        """After a syntax error, resume at the next entry that starts a line.

        Searching from the broken entry's start (not the current position)
        keeps an unclosed brace from swallowing every later entry.
        """
        match = _LINE_ENTRY_START.search(self.text, self.entry_start + 1)
        self.pos = match.start() if match else len(self.text)


def latex_to_text(value: str | None) -> str | None:
    """Convert common LaTeX markup to plain Unicode text."""
    if value is None:
        return None

    def accent(match: re.Match[str]) -> str:
        letter = match.group(2) or match.group(3)
        return unicodedata.normalize("NFC", letter + _ACCENTS[match.group(1)])

    value = _ACCENTED_DOTLESS.sub(r"\1{\2}", value)
    value = _SYMBOL_ACCENT.sub(accent, value)
    value = _LETTER_ACCENT.sub(accent, value)
    value = _SPECIAL_LETTER.sub(lambda m: _SPECIAL_LETTERS["\\" + m.group(1)], value)
    value = _ESCAPED_CHAR.sub(r"\1", value)
    value = value.replace("---", "\u2014").replace("--", "\u2013").replace("~", " ")
    value = value.replace("{", "").replace("}", "")
    return clean(value)


def _split_top_level_and(value: str) -> list[str]:
    """Split an author list on 'and' outside braces ({Barnes and Noble} stays whole)."""
    names, depth, start = [], 0, 0
    for i, char in enumerate(value):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif depth == 0 and (match := _AND.match(value, i)):
            names.append(value[start:i])
            start = match.end()
    names.append(value[start:])
    return [n for n in (latex_to_text(name) for name in names) if n and n.lower() != "others"]


def _lines_or_semicolons(value: str | None) -> list[str]:
    """WoS separates multi-valued fields by newline, Scopus by '; '."""
    if not value:
        return []
    parts = value.splitlines() if "\n" in value.strip() else value.split(";")
    return [p for p in (latex_to_text(part) for part in parts) if p]


def _keywords(value: str | None) -> list[str]:
    text = latex_to_text(value)
    return dedupe(split_list(text, ";" if text and ";" in text else ","))


def _is_scopus(fields: dict[str, str]) -> bool:
    return (
        fields.get("source", "").strip("{} ").lower() == "scopus"
    ) or "author_keywords" in fields


def _build_authors(fields: dict[str, str]) -> list[Author]:
    orcids: dict[str, str] = {}
    for entry in split_list(latex_to_text(fields.get("orcid-numbers"))):
        if match := _ORCID_ENTRY.match(entry):
            orcids[match.group("name").strip()] = match.group("id")
    return [
        Author(name=name, orcid=orcids.get(name))
        for name in _split_top_level_and(fields.get("author", ""))
    ]


def _to_record(entry: _Entry) -> Record | None:
    f = entry.fields

    def text(*names: str) -> str | None:
        for name in names:
            if (value := latex_to_text(f.get(name))) is not None:
                return value
        return None

    title = text("title")
    if not title:
        return None

    scopus = _is_scopus(f)
    if scopus:
        author_keywords, index_keywords = (
            _keywords(f.get("author_keywords")),
            _keywords(f.get("keywords")),
        )
        url = text("url")
        source_id = m.group(1) if url and (m := _SCOPUS_EID.search(url)) else None
        cited_by = parse_int(m.group(1)) if (m := _CITED_BY.search(f.get("note", ""))) else None
    else:
        author_keywords = _keywords(f.get("keywords") or f.get("author_keywords"))
        index_keywords = _keywords(f.get("keywords-plus"))
        source_id = text("unique-id")
        cited_by = parse_int(text("times-cited"))

    pages = text("pages")
    page_start, _, page_end = (pages or "").replace("\u2013", "-").partition("-")
    doc_type_raw = text("type") or entry.entry_type
    references = (
        _lines_or_semicolons(f.get("references"))
        if scopus
        else [
            r for r in (latex_to_text(x) for x in f.get("cited-references", "").splitlines()) if r
        ]
    )

    return Record(
        source_format=SourceFormat.BIBTEX,
        source_id=source_id,
        title=title,
        authors=_build_authors(f),
        year=parse_year(text("year", "date")),
        source_title=text("journal", "journaltitle", "booktitle"),
        source_abbrev=text("abbrev_source_title", "journal-iso", "shortjournal"),
        document_type=map_document_type(doc_type_raw, entry.entry_type),
        document_type_raw=doc_type_raw,
        abstract=text("abstract"),
        doi=normalize_doi(text("doi")),
        pmid=text("pubmed_id", "pubmed-id", "pmid"),
        issn=dedupe([v for v in (text("issn"), text("eissn")) if v]),
        volume=text("volume"),
        issue=text("number", "issue"),
        page_start=page_start.strip() or None,
        page_end=page_end.lstrip("-").strip() or None,
        article_number=text("art_number", "article-number", "eid"),
        language=text("language", "langid"),
        publisher=text("publisher"),
        author_keywords=author_keywords,
        index_keywords=index_keywords,
        affiliations=dedupe(_lines_or_semicolons(f.get("affiliations") or f.get("affiliation"))),
        cited_by=cited_by,
        references=references,
        url=text("url"),
    )


def parse_bibtex(text: str) -> ParseResult:
    scanner = _Scanner(text.lstrip("\ufeff"))
    records: list[Record] = []
    warnings: list[ParseWarning] = []
    index = 0
    while True:
        try:
            entry = scanner.next_entry()
        except BibtexSyntaxError as exc:
            warnings.append(ParseWarning(record_index=index, message=f"Entri rusak: {exc}."))
            index += 1
            scanner.recover()
            continue
        if entry is None:
            break
        record = _to_record(entry)
        if record is None:
            warnings.append(
                ParseWarning(record_index=index, message=f"Entri '{entry.key}' tanpa judul.")
            )
        else:
            records.append(record)
        index += 1
    return ParseResult(source_format=SourceFormat.BIBTEX, records=records, warnings=warnings)
