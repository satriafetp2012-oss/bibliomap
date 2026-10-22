"""Extract and normalize the entities that statistics and networks count.

Databases write the same author three ways ("Santoso, B", "Santoso B",
"Budi Santoso"), so every entity gets a normalized key for grouping plus a
display label chosen from the longest spelling seen. A user-editable
thesaurus can override both.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from bibliomap.schema import Record

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_INITIALS = re.compile(r"^(?:[a-z]\.?){1,4}$")
_PARENTHETICAL = re.compile(r"\s*\([^)]*\)")
# Trailing "Univ X, Dept Y, City, COUNTRY." — the country is the last part.
_AFFIL_SPLIT = re.compile(r"\s*,\s*")
_POSTCODE = re.compile(r"\b[A-Z]{2}\s*\d{5}\b|\b\d{4,6}\b")

#: Closed list of country names. Anything else in the tail of an
#: affiliation (a US state, a city, a postcode) is not a country.
_COUNTRIES = {
    "afghanistan": "Afghanistan",
    "albania": "Albania",
    "algeria": "Algeria",
    "andorra": "Andorra",
    "angola": "Angola",
    "arabia": "Arabia",
    "argentina": "Argentina",
    "armenia": "Armenia",
    "australia": "Australia",
    "austria": "Austria",
    "azerbaijan": "Azerbaijan",
    "bahrain": "Bahrain",
    "bangladesh": "Bangladesh",
    "barbados": "Barbados",
    "belarus": "Belarus",
    "belgium": "Belgium",
    "belize": "Belize",
    "benin": "Benin",
    "bhutan": "Bhutan",
    "bolivia": "Bolivia",
    "bosnia": "Bosnia",
    "botswana": "Botswana",
    "brazil": "Brazil",
    "brunei": "Brunei",
    "bulgaria": "Bulgaria",
    "burkina": "Burkina",
    "burkina faso": "Burkina Faso",
    "burundi": "Burundi",
    "cambodia": "Cambodia",
    "cameroon": "Cameroon",
    "canada": "Canada",
    "chad": "Chad",
    "chile": "Chile",
    "china": "China",
    "colombia": "Colombia",
    "congo": "Congo",
    "costa": "Costa",
    "costa rica": "Costa Rica",
    "croatia": "Croatia",
    "cuba": "Cuba",
    "cyprus": "Cyprus",
    "czechia": "Czechia",
    "denmark": "Denmark",
    "dominican": "Dominican",
    "dominican republic": "Dominican Republic",
    "ecuador": "Ecuador",
    "egypt": "Egypt",
    "el salvador": "El Salvador",
    "estonia": "Estonia",
    "eswatini": "Eswatini",
    "ethiopia": "Ethiopia",
    "faso": "Faso",
    "fiji": "Fiji",
    "finland": "Finland",
    "france": "France",
    "gabon": "Gabon",
    "gambia": "Gambia",
    "georgia": "Georgia",
    "germany": "Germany",
    "ghana": "Ghana",
    "greece": "Greece",
    "guatemala": "Guatemala",
    "guinea": "Guinea",
    "guyana": "Guyana",
    "haiti": "Haiti",
    "honduras": "Honduras",
    "hungary": "Hungary",
    "iceland": "Iceland",
    "india": "India",
    "indonesia": "Indonesia",
    "iran": "Iran",
    "iraq": "Iraq",
    "ireland": "Ireland",
    "israel": "Israel",
    "italy": "Italy",
    "jamaica": "Jamaica",
    "japan": "Japan",
    "jordan": "Jordan",
    "kazakhstan": "Kazakhstan",
    "kenya": "Kenya",
    "kuwait": "Kuwait",
    "kyrgyzstan": "Kyrgyzstan",
    "lanka": "Lanka",
    "laos": "Laos",
    "latvia": "Latvia",
    "lebanon": "Lebanon",
    "liberia": "Liberia",
    "libya": "Libya",
    "lithuania": "Lithuania",
    "luxembourg": "Luxembourg",
    "macedonia": "Macedonia",
    "madagascar": "Madagascar",
    "malawi": "Malawi",
    "malaysia": "Malaysia",
    "maldives": "Maldives",
    "mali": "Mali",
    "malta": "Malta",
    "mauritania": "Mauritania",
    "mauritius": "Mauritius",
    "mexico": "Mexico",
    "moldova": "Moldova",
    "monaco": "Monaco",
    "mongolia": "Mongolia",
    "montenegro": "Montenegro",
    "morocco": "Morocco",
    "mozambique": "Mozambique",
    "myanmar": "Myanmar",
    "namibia": "Namibia",
    "nepal": "Nepal",
    "netherlands": "Netherlands",
    "new zealand": "New Zealand",
    "nicaragua": "Nicaragua",
    "niger": "Niger",
    "nigeria": "Nigeria",
    "north": "North",
    "north macedonia": "North Macedonia",
    "norway": "Norway",
    "oman": "Oman",
    "pakistan": "Pakistan",
    "palestine": "Palestine",
    "panama": "Panama",
    "paraguay": "Paraguay",
    "peru": "Peru",
    "philippines": "Philippines",
    "poland": "Poland",
    "portugal": "Portugal",
    "qatar": "Qatar",
    "republic": "Republic",
    "rica": "Rica",
    "romania": "Romania",
    "russia": "Russia",
    "rwanda": "Rwanda",
    "salvador": "Salvador",
    "saudi": "Saudi",
    "saudi arabia": "Saudi Arabia",
    "senegal": "Senegal",
    "serbia": "Serbia",
    "singapore": "Singapore",
    "slovakia": "Slovakia",
    "slovenia": "Slovenia",
    "somalia": "Somalia",
    "spain": "Spain",
    "sri lanka": "Sri Lanka",
    "sudan": "Sudan",
    "suriname": "Suriname",
    "sweden": "Sweden",
    "switzerland": "Switzerland",
    "syria": "Syria",
    "tanzania": "Tanzania",
    "thailand": "Thailand",
    "tobago": "Tobago",
    "togo": "Togo",
    "trinidad": "Trinidad",
    "trinidad tobago": "Trinidad Tobago",
    "tunisia": "Tunisia",
    "turkey": "Turkey",
    "turkmenistan": "Turkmenistan",
    "uganda": "Uganda",
    "ukraine": "Ukraine",
    "uruguay": "Uruguay",
    "uzbekistan": "Uzbekistan",
    "venezuela": "Venezuela",
    "vietnam": "Vietnam",
    "yemen": "Yemen",
    "zambia": "Zambia",
    "zealand": "Zealand",
    "zimbabwe": "Zimbabwe",
}

#: Spellings that differ across databases, plus sub-national entities that
#: appear where a country is expected.
_COUNTRY_ALIASES = {
    "usa": "United States",
    "united states of america": "United States",
    "u s a": "United States",
    "united states": "United States",
    "uk": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "wales": "United Kingdom",
    "north ireland": "United Kingdom",
    "united kingdom": "United Kingdom",
    "peoples r china": "China",
    "p r china": "China",
    "china": "China",
    "taiwan": "Taiwan",
    "south korea": "South Korea",
    "korea": "South Korea",
    "russia": "Russia",
    "viet nam": "Vietnam",
    "republic of korea": "South Korea",
    "korea rep": "South Korea",
    "republic of china": "Taiwan",
    "roc": "Taiwan",
    "taiwan roc": "Taiwan",
    "hong kong": "Hong Kong",
    "macau": "Macau",
    "czech republic": "Czechia",
    "slovak republic": "Slovakia",
    "u arab emirates": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "deutschland": "Germany",
    "espana": "Spain",
    "brasil": "Brazil",
    "nederland": "Netherlands",
}

#: Word stems that mark an organization. Exports abbreviate heavily
#: ("Harvard Med Sch", "Univ Gadjah Mada"), so these match as substrings.
_ORG_MARKERS = (
    "univ",
    "institut",
    "college",
    "school",
    " sch",
    "hosp",
    "acad",
    "minist",
    "agency",
    "council",
    "foundation",
    "polytech",
    "politek",
)
#: Subdivisions that are never the organization itself.
_UNIT_MARKERS = ("dept", "department", "fac ", "faculty", "div ", "division", "lab", "ctr", "unit")


class EntityKind(StrEnum):
    AUTHOR = "author"
    SOURCE = "source"
    KEYWORD = "keyword"
    INDEX_KEYWORD = "index_keyword"
    AFFILIATION = "affiliation"
    COUNTRY = "country"
    REFERENCE = "reference"
    DOCUMENT = "document"


@dataclass(frozen=True)
class Mention:
    """One entity occurrence in one document."""

    key: str
    label: str


@dataclass
class Thesaurus:
    """User-supplied replacements, applied to normalized keys.

    ``replace`` maps a key to the label it should be merged into; ``drop``
    removes a key from every analysis (stop words, "Anonymous", and so on).
    """

    replace: dict[str, str] = field(default_factory=dict)
    drop: set[str] = field(default_factory=set)

    @classmethod
    def from_pairs(cls, replace: dict[str, str], drop: Iterable[str]) -> Thesaurus:
        return cls(
            replace={normalize_key(k): v for k, v in replace.items()},
            drop={normalize_key(d) for d in drop},
        )


def normalize_key(value: str) -> str:
    """Case-fold, strip accents and punctuation; the grouping key."""
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return " ".join(_NON_ALNUM.sub(" ", text).split())


def author_key(name: str) -> str | None:
    """Surname plus every given-name initial.

    'Santoso, Budi', 'Santoso B' and 'Budi Santoso' all give 'santoso b'.

    Keeping every initial matters: on a real corpus, collapsing to the first
    initial alone merged ten distinct researchers into a single 'Lee S',
    which would make that node the most productive author in the field.
    The cost is that one database writing 'Santoso, Budi Setiawan' and
    another 'Santoso, Budi' split; a thesaurus entry merges those.
    """
    cleaned = _PARENTHETICAL.sub("", name).strip().rstrip(".")
    if not cleaned:
        return None
    if "," in cleaned:
        surname, _, rest = cleaned.partition(",")
        given = rest
    else:
        parts = cleaned.split()
        if len(parts) == 1:
            surname, given = parts[0], ""
        elif _INITIALS.match(normalize_key(parts[-1]).replace(" ", "")):
            # "Santoso B" / "Santoso BS"
            surname, given = " ".join(parts[:-1]), parts[-1]
        else:
            # "Budi Santoso"
            surname, given = parts[-1], " ".join(parts[:-1])
    surname_key = normalize_key(surname)
    if not surname_key:
        return None
    return f"{surname_key} {_initials(given)}".strip()


def _initials(given: str) -> str:
    """Initials of a given-name string.

    Exports write them two ways: as names ('Mei-Ling' -> 'ml') or as a run
    of capitals ('DH' -> 'dh'). A short all-caps word is the second kind.
    """
    letters: list[str] = []
    for word in re.split(r"[^0-9A-Za-z]+", _strip_accents(given)):
        if not word:
            continue
        if word.isupper() and len(word) <= 3:
            letters.extend(word.lower())
        else:
            letters.append(word[0].lower())
    return "".join(letters)


def _strip_accents(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()


def country_from_affiliation(affiliation: str) -> str | None:
    """Last comma-separated part of a WoS/Scopus style affiliation."""
    parts = [p for p in _AFFIL_SPLIT.split(affiliation.strip().rstrip(".")) if p.strip()]
    if not parts:
        return None
    tail = _POSTCODE.sub("", parts[-1]).strip()
    key = normalize_key(tail)
    if not key:
        return None
    if key in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[key]
    if key in _COUNTRIES:
        return _COUNTRIES[key]
    # Some exports append the country after a state: "Boston, MA 02115 USA".
    for word_count in (2, 1):
        words = key.split()
        if len(words) > word_count:
            suffix = " ".join(words[-word_count:])
            if suffix in _COUNTRY_ALIASES:
                return _COUNTRY_ALIASES[suffix]
            if suffix in _COUNTRIES:
                return _COUNTRIES[suffix]
    return None


def organization_from_affiliation(affiliation: str) -> str | None:
    """First part that looks like an organization rather than a department."""
    parts = [p.strip() for p in _AFFIL_SPLIT.split(affiliation.strip().rstrip(".")) if p.strip()]
    if not parts:
        return None
    for part in parts:
        key = f" {normalize_key(part)} "
        if any(marker in key for marker in _ORG_MARKERS):
            return part
    # No recognizable organization: take the first part that is not a
    # department, faculty or laboratory of something else.
    for part in parts:
        key = f" {normalize_key(part)} "
        if not any(marker in key for marker in _UNIT_MARKERS):
            return part
    return parts[0]


def _mentions(
    values: Iterable[str], key_of: Callable[[str], str | None], thesaurus: Thesaurus
) -> list[Mention]:
    """Normalize values into unique mentions for one document."""
    seen: dict[str, str] = {}
    for value in values:
        raw = value.strip()
        if not raw:
            continue
        key = key_of(raw)
        if key is None or not key:
            continue
        if key in thesaurus.drop:
            continue
        if (replacement := thesaurus.replace.get(key)) is not None:
            raw, key = replacement, normalize_key(replacement)
            if key in thesaurus.drop:
                continue
        # Longest spelling wins: "Santoso, Budi" over "Santoso, B".
        if key not in seen or len(raw) > len(seen[key]):
            seen[key] = raw
    return [Mention(key=k, label=v) for k, v in seen.items()]


def extract(record: Record, kind: EntityKind, thesaurus: Thesaurus | None = None) -> list[Mention]:
    """Entities of one kind mentioned by one record, deduplicated."""
    th = thesaurus or Thesaurus()
    match kind:
        case EntityKind.AUTHOR:
            names = [a.full_name or a.name for a in record.authors]
            return _mentions(names, author_key, th)
        case EntityKind.SOURCE:
            return _mentions([record.source_title or ""], normalize_key, th)
        case EntityKind.KEYWORD:
            return _mentions(record.author_keywords, normalize_key, th)
        case EntityKind.INDEX_KEYWORD:
            return _mentions(record.index_keywords, normalize_key, th)
        case EntityKind.AFFILIATION:
            affiliations = record.affiliations or [
                a for author in record.authors for a in author.affiliations
            ]
            return _mentions(affiliations, _org_key, th)
        case EntityKind.COUNTRY:
            affiliations = record.affiliations or [
                a for author in record.authors for a in author.affiliations
            ]
            countries = [c for a in affiliations if (c := country_from_affiliation(a))]
            return _mentions(countries, normalize_key, th)
        case EntityKind.REFERENCE:
            return _mentions(record.references, normalize_key, th)
        case EntityKind.DOCUMENT:
            return _mentions([document_label(record)], normalize_key, th)


def _org_key(affiliation: str) -> str | None:
    org = organization_from_affiliation(affiliation)
    return normalize_key(org) if org else None


def document_label(record: Record) -> str:
    """Short citation label: 'Santoso B, 2021, Inj Prev'."""
    author = record.authors[0].name.replace(",", "") if record.authors else "Anon"
    parts = [author, str(record.year) if record.year else "n.d."]
    if source := (record.source_abbrev or record.source_title):
        parts.append(source[:40])
    return ", ".join(parts)


@dataclass(frozen=True)
class EntityIndex:
    """Entities of one kind across a corpus, with their document ids."""

    kind: EntityKind
    labels: dict[str, str]
    documents: dict[str, list[int]]
    #: Document id -> the entity keys it mentions, in record order.
    by_document: dict[int, list[str]]

    def occurrences(self, key: str) -> int:
        return len(self.documents.get(key, ()))

    def top(self, limit: int) -> list[tuple[str, int]]:
        counts = Counter({k: len(v) for k, v in self.documents.items()})
        return counts.most_common(limit)


def build_index(
    records: dict[int, Record], kind: EntityKind, thesaurus: Thesaurus | None = None
) -> EntityIndex:
    labels: dict[str, str] = {}
    documents: dict[str, list[int]] = defaultdict(list)
    by_document: dict[int, list[str]] = {}

    for doc_id, record in records.items():
        keys: list[str] = []
        for mention in extract(record, kind, thesaurus):
            documents[mention.key].append(doc_id)
            keys.append(mention.key)
            if mention.key not in labels or len(mention.label) > len(labels[mention.key]):
                labels[mention.key] = mention.label
        by_document[doc_id] = keys

    return EntityIndex(kind=kind, labels=labels, documents=dict(documents), by_document=by_document)
