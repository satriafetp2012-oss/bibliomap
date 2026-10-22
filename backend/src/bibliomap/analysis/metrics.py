"""Bibliometric statistics: descriptive counts, Lotka, Bradford, h/g/m-index.

Methods follow the published definitions:
- Lotka (1926): share of authors with n publications, fitted as a power law
  by least squares on log counts, as bibliometrix does.
- Bradford (1934): sources sorted by productivity and split into three
  zones of roughly equal article counts.
- Hirsch (2005) h-index, Egghe (2006) g-index, Hirsch m-index (h / years
  active).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel

from bibliomap.analysis.entities import EntityIndex, EntityKind, build_index
from bibliomap.schema import Record


class YearCount(BaseModel):
    year: int
    count: int
    mean_citations: float | None = None


class Overview(BaseModel):
    documents: int
    sources: int
    authors: int
    single_authored: int
    keywords_author: int
    keywords_index: int
    references: int
    year_min: int | None
    year_max: int | None
    mean_citations: float
    total_citations: int
    mean_authors_per_document: float
    collaboration_index: float | None
    international_coauthorship_pct: float | None
    annual_growth_rate_pct: float | None
    documents_per_year: list[YearCount]
    document_types: dict[str, int]


class RankedEntity(BaseModel):
    key: str
    label: str
    documents: int
    citations: int
    h_index: int
    g_index: int
    m_index: float | None
    first_year: int | None


class LotkaRow(BaseModel):
    documents_written: int
    authors: int
    proportion: float
    fitted_proportion: float


class LotkaFit(BaseModel):
    rows: list[LotkaRow]
    exponent: float
    constant: float
    r_squared: float
    #: Kolmogorov-Smirnov distance against the fitted law.
    ks_statistic: float


class BradfordRow(BaseModel):
    rank: int
    key: str
    label: str
    documents: int
    cumulative: int
    zone: int


class BradfordAnalysis(BaseModel):
    rows: list[BradfordRow]
    zone_sources: list[int]
    zone_documents: list[int]
    #: Ratio between successive zone sizes; Bradford's law predicts ~constant.
    multiplier: float | None
    #: Documents that name a source, and those that do not (books, reports).
    documents_covered: int = 0
    documents_without_source: int = 0


def _years(records: list[Record]) -> list[int]:
    return [r.year for r in records if r.year is not None]


def h_index(citations: list[int]) -> int:
    """Largest h with at least h items cited at least h times."""
    return sum(1 for i, c in enumerate(sorted(citations, reverse=True), start=1) if c >= i)


def g_index(citations: list[int]) -> int:
    """Largest g where the top g items together have at least g^2 citations."""
    total = 0
    for i, c in enumerate(sorted(citations, reverse=True), start=1):
        total += c
        if total < i * i:
            return i - 1
    return len(citations)


def m_index(h: int, first_year: int | None, current_year: int) -> float | None:
    """h divided by years since the first publication."""
    if first_year is None:
        return None
    years = current_year - first_year + 1
    return round(h / years, 3) if years > 0 else None


def annual_growth_rate(per_year: list[YearCount]) -> float | None:
    """Compound annual growth rate between the first and last year, in percent."""
    usable = [y for y in per_year if y.count > 0]
    if len(usable) < 2:
        return None
    first, last = usable[0], usable[-1]
    span = last.year - first.year
    if span <= 0 or first.count <= 0:
        return None
    growth: float = (last.count / first.count) ** (1 / span) - 1
    return round(growth * 100, 2)


def overview(records: dict[int, Record]) -> Overview:
    values = list(records.values())
    years = _years(values)
    citations = [r.cited_by or 0 for r in values]
    authors_index = build_index(records, EntityKind.AUTHOR)
    countries_index = build_index(records, EntityKind.COUNTRY)

    per_year_counts = Counter(years)
    citations_by_year: dict[int, list[int]] = {}
    for record in values:
        if record.year is not None:
            citations_by_year.setdefault(record.year, []).append(record.cited_by or 0)
    per_year = [
        YearCount(
            year=year,
            count=count,
            mean_citations=round(sum(citations_by_year[year]) / count, 2) if count else None,
        )
        for year, count in sorted(per_year_counts.items())
    ]

    author_counts = [len(authors_index.by_document[doc_id]) for doc_id in records]
    multi_authored = [n for n in author_counts if n > 1]
    with_countries = [
        doc_id for doc_id in records if len(set(countries_index.by_document[doc_id])) > 1
    ]
    known_countries = [doc_id for doc_id in records if countries_index.by_document[doc_id]]

    return Overview(
        documents=len(values),
        sources=len(build_index(records, EntityKind.SOURCE).documents),
        authors=len(authors_index.documents),
        single_authored=sum(1 for n in author_counts if n == 1),
        keywords_author=len(build_index(records, EntityKind.KEYWORD).documents),
        keywords_index=len(build_index(records, EntityKind.INDEX_KEYWORD).documents),
        references=sum(len(r.references) for r in values),
        year_min=min(years, default=None),
        year_max=max(years, default=None),
        mean_citations=round(sum(citations) / len(values), 2) if values else 0.0,
        total_citations=sum(citations),
        mean_authors_per_document=round(sum(author_counts) / len(values), 2) if values else 0.0,
        # Collaboration index: mean authors per multi-authored document.
        collaboration_index=(
            round(sum(multi_authored) / len(multi_authored), 2) if multi_authored else None
        ),
        international_coauthorship_pct=(
            round(100 * len(with_countries) / len(known_countries), 2) if known_countries else None
        ),
        annual_growth_rate_pct=annual_growth_rate(per_year),
        documents_per_year=per_year,
        document_types=dict(Counter(r.document_type.value for r in values).most_common()),
    )


def rank_entities(
    records: dict[int, Record], kind: EntityKind, limit: int = 20, current_year: int | None = None
) -> list[RankedEntity]:
    """Most productive entities with their impact metrics."""
    index = build_index(records, kind)
    year_now = current_year or max((r.year for r in records.values() if r.year), default=0)
    ranked: list[RankedEntity] = []

    for key, doc_ids in index.documents.items():
        citations = [records[d].cited_by or 0 for d in doc_ids]
        years = [y for d in doc_ids if (y := records[d].year) is not None]
        h = h_index(citations)
        first_year = min(years) if years else None
        ranked.append(
            RankedEntity(
                key=key,
                label=index.labels[key],
                documents=len(doc_ids),
                citations=sum(citations),
                h_index=h,
                g_index=g_index(citations),
                m_index=m_index(h, first_year, year_now) if year_now else None,
                first_year=first_year,
            )
        )
    ranked.sort(key=lambda e: (-e.documents, -e.citations, e.label))
    return ranked[:limit]


@dataclass
class _Fit:
    exponent: float
    constant: float
    r_squared: float


def _least_squares(xs: list[float], ys: list[float]) -> _Fit:
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    slope = sxy / sxx if sxx else 0.0
    intercept = mean_y - slope * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys, strict=True))
    r_squared = 1 - ss_res / ss_tot if ss_tot else 1.0
    return _Fit(exponent=-slope, constant=intercept, r_squared=round(r_squared, 4))


def lotka(records: dict[int, Record], index: EntityIndex | None = None) -> LotkaFit:
    """Author productivity distribution and its fitted power law."""
    authors = index or build_index(records, EntityKind.AUTHOR)
    per_author = Counter(len(docs) for docs in authors.documents.values())
    total_authors = sum(per_author.values())
    if total_authors == 0:
        return LotkaFit(rows=[], exponent=0.0, constant=0.0, r_squared=0.0, ks_statistic=0.0)

    points = sorted(per_author.items())
    xs = [math.log10(n) for n, _ in points]
    ys = [math.log10(count) for _, count in points]
    fit = _least_squares(xs, ys) if len(points) > 1 else _Fit(0.0, ys[0], 1.0)

    # Fitted proportions renormalized so they sum to 1 over the observed range.
    raw = {n: n**-fit.exponent for n, _ in points}
    scale = sum(raw.values())
    rows = [
        LotkaRow(
            documents_written=n,
            authors=count,
            proportion=round(count / total_authors, 4),
            fitted_proportion=round(raw[n] / scale, 4) if scale else 0.0,
        )
        for n, count in points
    ]

    observed = 0.0
    expected = 0.0
    ks = 0.0
    for row in rows:
        observed += row.proportion
        expected += row.fitted_proportion
        ks = max(ks, abs(observed - expected))

    return LotkaFit(
        rows=rows,
        exponent=round(fit.exponent, 4),
        constant=round(10**fit.constant / total_authors, 4),
        r_squared=fit.r_squared,
        ks_statistic=round(ks, 4),
    )


def bradford(records: dict[int, Record], zones: int = 3) -> BradfordAnalysis:
    """Rank sources by productivity and split them into Bradford zones.

    Documents with no source (books, reports) are excluded: Bradford's law
    describes journal scatter. The counts say how many were left out.
    """
    index = build_index(records, EntityKind.SOURCE)
    counts = sorted(
        ((key, len(docs)) for key, docs in index.documents.items()),
        key=lambda item: (-item[1], index.labels[item[0]]),
    )
    total = sum(c for _, c in counts)
    if total == 0:
        return BradfordAnalysis(
            rows=[],
            zone_sources=[],
            zone_documents=[],
            multiplier=None,
            documents_without_source=len(records),
        )

    # Zone boundaries follow Bradford's convention, as implemented in
    # bibliometrix: a zone ends at the first source whose cumulative count
    # passes its share of the total.
    cumulative: list[int] = []
    running = 0
    for _, count in counts:
        running += count
        cumulative.append(running)

    bounds: list[int] = []
    for zone in range(1, zones):
        share = total * zone / zones
        bounds.append(min(sum(1 for c in cumulative if c <= share) + 1, len(counts)))

    def zone_of(rank: int) -> int:
        for zone, bound in enumerate(bounds, start=1):
            if rank <= bound:
                return zone
        return zones

    rows: list[BradfordRow] = []
    zone_sources = [0] * zones
    zone_documents = [0] * zones
    for rank, (key, count) in enumerate(counts, start=1):
        zone = zone_of(rank)
        rows.append(
            BradfordRow(
                rank=rank,
                key=key,
                label=index.labels[key],
                documents=count,
                cumulative=cumulative[rank - 1],
                zone=zone,
            )
        )
        zone_sources[zone - 1] += 1
        zone_documents[zone - 1] += count

    multipliers = [
        zone_sources[i + 1] / zone_sources[i]
        for i in range(zones - 1)
        if zone_sources[i] and zone_sources[i + 1]
    ]
    return BradfordAnalysis(
        rows=rows,
        zone_sources=zone_sources,
        zone_documents=zone_documents,
        multiplier=round(sum(multipliers) / len(multipliers), 2) if multipliers else None,
        documents_covered=total,
        documents_without_source=len(records) - total,
    )
