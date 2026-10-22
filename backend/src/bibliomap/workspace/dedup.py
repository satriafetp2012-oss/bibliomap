"""Duplicate detection across imports.

Strategy:
1. Candidate pairs come from an exact DOI index plus a sorted-neighbourhood
   pass over normalized titles (sorted forwards and reversed, so a typo at
   either end of a title still lands near its twin).
2. Each pair is scored. Clear matches are merged automatically; borderline
   ones go to a manual review queue. Thresholds favour precision: a wrong
   automatic merge silently loses a study, a missed one only costs a review.
3. Manual decisions override the automatic rules, and groups are formed with
   union-find.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum

from rapidfuzz import fuzz

from bibliomap.schema import Record

WINDOW = 10
AUTO_TITLE_WITH_DOI = 80
AUTO_TITLE_NO_DOI = 98
REVIEW_TITLE_NO_DOI = 92
REVIEW_TITLE_DOI_CONFLICT = 97
# Titles shorter than this ("Editorial", "Reply to letter") are too generic
# to merge without a DOI.
MIN_SAFE_TITLE_CHARS = 20
# One database may drop a subtitle ("Title: subtitle" vs "Title").
MIN_PREFIX_TITLE_CHARS = 30

_TAG = re.compile(r"<[^>]+>")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_INITIALS = re.compile(r"^(?:[A-Z]\.?){1,3}$|^[A-Z]{1,3}$")


@dataclass(frozen=True)
class StoredRecord:
    """A record as kept in a workspace: stable id plus its import."""

    id: int
    import_id: int
    record: Record


class MatchLevel(StrEnum):
    AUTO = "auto"
    REVIEW = "review"


@dataclass(frozen=True)
class CandidatePair:
    a: int
    b: int
    level: MatchLevel
    title_similarity: int
    reasons: tuple[str, ...]


@dataclass
class DedupOutcome:
    groups: list[list[int]] = field(default_factory=list)
    pending: list[CandidatePair] = field(default_factory=list)
    auto_pairs: int = 0
    manual_merges: int = 0

    @property
    def duplicates_removed(self) -> int:
        return sum(len(g) - 1 for g in self.groups)


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    text = unicodedata.normalize("NFKD", _TAG.sub(" ", title))
    text = text.encode("ascii", "ignore").decode().lower()
    return " ".join(_NON_ALNUM.sub(" ", text).split())


def first_author_surname(record: Record) -> str | None:
    """Surname of the first author across name orders used by exporters.

    'Santoso, B' / 'Santoso B' (PubMed) / 'Budi Santoso' (Lens, OpenAlex).
    """
    if not record.authors:
        return None
    name = record.authors[0].name.strip()
    if "," in name:
        surname = name.split(",", 1)[0]
    else:
        parts = name.split()
        if not parts:
            return None
        # A trailing initials token means "Surname Initials".
        surname = parts[0] if len(parts) > 1 and _INITIALS.match(parts[-1]) else parts[-1]
    return normalize_title(surname) or None


@dataclass(frozen=True)
class _Key:
    id: int
    title: str
    doi: str | None
    year: int | None
    surname: str | None
    source: str


def _key(item: StoredRecord) -> _Key:
    rec = item.record
    return _Key(
        id=item.id,
        title=normalize_title(rec.title),
        doi=rec.doi,
        year=rec.year,
        surname=first_author_surname(rec),
        source=normalize_title(rec.source_title),
    )


def compare(a: _Key, b: _Key) -> CandidatePair | None:
    """Score one pair; None means 'not a duplicate'."""
    if not a.title or not b.title:
        return None
    similarity = round(fuzz.ratio(a.title, b.title))
    years_close = a.year is None or b.year is None or abs(a.year - b.year) <= 1
    same_year = a.year is not None and a.year == b.year
    authors_known = a.surname is not None and b.surname is not None
    same_author = authors_known and a.surname == b.surname
    author_compatible = not authors_known or same_author
    short_title = min(len(a.title), len(b.title)) < MIN_SAFE_TITLE_CHARS

    reasons = [f"title:{similarity}"]
    if same_year:
        reasons.append("year_equal")
    if same_author:
        reasons.append("first_author_equal")

    def pair(level: MatchLevel) -> CandidatePair:
        lo, hi = sorted((a.id, b.id))
        return CandidatePair(lo, hi, level, similarity, tuple(reasons))

    if a.doi and b.doi:
        if a.doi == b.doi:
            reasons.insert(0, "doi_equal")
            # Same DOI but different titles: e.g. chapters sharing a book DOI.
            return pair(MatchLevel.AUTO if similarity >= AUTO_TITLE_WITH_DOI else MatchLevel.REVIEW)
        if similarity >= REVIEW_TITLE_DOI_CONFLICT and years_close and author_compatible:
            # Preprint vs. published version, or a corrigendum.
            reasons.insert(0, "doi_different")
            return pair(MatchLevel.REVIEW)
        return None

    if short_title:
        if similarity == 100 and same_year and same_author and a.source and a.source == b.source:
            reasons.append("short_title")
            return pair(MatchLevel.REVIEW)
        return None
    if similarity >= AUTO_TITLE_NO_DOI and (same_year or a.year is None or b.year is None):
        if same_author:
            return pair(MatchLevel.AUTO)
        if author_compatible:
            return pair(MatchLevel.REVIEW)
    if similarity >= REVIEW_TITLE_NO_DOI and years_close and author_compatible:
        return pair(MatchLevel.REVIEW)
    shorter, longer = sorted((a.title, b.title), key=len)
    if (
        len(shorter) >= MIN_PREFIX_TITLE_CHARS
        and longer.startswith(shorter)
        and same_year
        and same_author
    ):
        reasons.append("title_prefix")
        return pair(MatchLevel.REVIEW)
    return None


def _candidate_ids(keys: list[_Key]) -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()

    by_doi: dict[str, list[int]] = defaultdict(list)
    for k in keys:
        if k.doi:
            by_doi[k.doi].append(k.id)
    for ids in by_doi.values():
        pairs.update((x, y) for i, x in enumerate(ids) for y in ids[i + 1 :])

    titled = [k for k in keys if k.title]
    for order in (
        sorted(titled, key=lambda k: k.title),
        sorted(titled, key=lambda k: k.title[::-1]),
    ):
        for i, k in enumerate(order):
            for other in order[i + 1 : i + 1 + WINDOW]:
                pairs.add((min(k.id, other.id), max(k.id, other.id)))
    return pairs


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # Keep the smallest id as root so group ids are stable.
            self.parent[max(ra, rb)] = min(ra, rb)


def find_duplicates(
    items: list[StoredRecord], decisions: dict[tuple[int, int], bool] | None = None
) -> DedupOutcome:
    """Group duplicate records.

    ``decisions`` maps an ordered (low id, high id) pair to the user's verdict:
    True merges the pair, False keeps it apart even if the rules would merge it.
    """
    decisions = decisions or {}
    keys = {k.id: k for k in (_key(item) for item in items)}
    uf = _UnionFind()
    outcome = DedupOutcome()
    review: list[CandidatePair] = []

    for a_id, b_id in _candidate_ids(list(keys.values())):
        match = compare(keys[a_id], keys[b_id])
        if match is None:
            continue
        verdict = decisions.get((match.a, match.b))
        if verdict is False:
            continue
        if match.level is MatchLevel.AUTO and verdict is None:
            uf.union(match.a, match.b)
            outcome.auto_pairs += 1
        elif verdict is None:
            review.append(match)

    for (a_id, b_id), same in decisions.items():
        if same and a_id in keys and b_id in keys:
            uf.union(a_id, b_id)
            outcome.manual_merges += 1

    members: dict[int, list[int]] = defaultdict(list)
    for record_id in keys:
        members[uf.find(record_id)].append(record_id)
    outcome.groups = sorted(sorted(g) for g in members.values() if len(g) > 1)
    outcome.pending = sorted(
        (p for p in review if uf.find(p.a) != uf.find(p.b)),
        key=lambda p: (-p.title_similarity, p.a, p.b),
    )
    return outcome
