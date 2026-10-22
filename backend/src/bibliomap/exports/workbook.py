"""Excel workbook and CSV exports of a workspace's records and statistics."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from bibliomap.api.analysis import Statistics
from bibliomap.schema import Record
from bibliomap.workspace.filters import ExclusionReason
from bibliomap.workspace.merge import MergedRecord
from bibliomap.workspace.prisma import PrismaFlow

#: Excel refuses strings longer than this in a cell.
MAX_CELL_CHARS = 32_000
_MAX_WIDTH = 60

RECORD_COLUMNS = [
    ("id", "ID"),
    ("source_format", "Format sumber"),
    ("source_id", "ID asal"),
    ("title", "Judul"),
    ("authors", "Penulis"),
    ("year", "Tahun"),
    ("source_title", "Sumber"),
    ("document_type", "Jenis dokumen"),
    ("doi", "DOI"),
    ("pmid", "PMID"),
    ("volume", "Volume"),
    ("issue", "Nomor"),
    ("pages", "Halaman"),
    ("cited_by", "Sitasi"),
    ("language", "Bahasa"),
    ("publisher", "Penerbit"),
    ("author_keywords", "Kata kunci penulis"),
    ("index_keywords", "Kata kunci indeks"),
    ("affiliations", "Afiliasi"),
    ("abstract", "Abstrak"),
    ("references", "Referensi"),
    ("imports", "Jumlah sumber impor"),
    ("exclusion_reason", "Alasan tersaring"),
]


def _clip(value: str) -> str:
    return value if len(value) <= MAX_CELL_CHARS else value[: MAX_CELL_CHARS - 1] + "…"


def record_row(
    item: MergedRecord, reason: ExclusionReason | None = None
) -> dict[str, str | int | None]:
    record: Record = item.record
    pages = "-".join(p for p in (record.page_start, record.page_end) if p) or record.article_number
    return {
        "id": item.id,
        "source_format": record.source_format.value,
        "source_id": record.source_id,
        "title": _clip(record.title),
        "authors": _clip("; ".join(a.full_name or a.name for a in record.authors)),
        "year": record.year,
        "source_title": record.source_title,
        "document_type": record.document_type.value,
        "doi": record.doi,
        "pmid": record.pmid,
        "volume": record.volume,
        "issue": record.issue,
        "pages": pages,
        "cited_by": record.cited_by,
        "language": record.language,
        "publisher": record.publisher,
        "author_keywords": _clip("; ".join(record.author_keywords)),
        "index_keywords": _clip("; ".join(record.index_keywords)),
        "affiliations": _clip("; ".join(record.affiliations)),
        "abstract": _clip(record.abstract or ""),
        "references": _clip("; ".join(record.references)),
        "imports": len({s.import_id for s in item.sources}),
        "exclusion_reason": reason.value if reason else None,
    }


def records_csv(rows: Iterable[dict[str, str | int | None]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=[key for key, _ in RECORD_COLUMNS], lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    # A BOM makes Excel open UTF-8 CSV correctly on Windows.
    return "\ufeff" + buffer.getvalue()


def _sheet(
    book: Workbook, title: str, header: Sequence[str], rows: Iterable[Sequence[Any]]
) -> Worksheet:
    sheet: Worksheet = book.create_sheet(title[:31])
    sheet.append(list(header))
    for row in rows:
        sheet.append(list(row))
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(vertical="top")
    sheet.freeze_panes = "A2"
    for index, name in enumerate(header, start=1):
        longest = max(
            (
                len(str(sheet.cell(row=r, column=index).value or ""))
                for r in range(1, min(sheet.max_row, 200) + 1)
            ),
            default=len(name),
        )
        sheet.column_dimensions[get_column_letter(index)].width = min(
            max(len(name) + 2, longest + 2), _MAX_WIDTH
        )
    return sheet


def _pairs(sheet_rows: list[tuple[str, Any]]) -> list[Sequence[Any]]:
    return [[label, value if value is not None else "\u2013"] for label, value in sheet_rows]


def build_workbook(
    *,
    kept: list[MergedRecord],
    excluded: list[tuple[MergedRecord, ExclusionReason]],
    statistics: Statistics,
    prisma: PrismaFlow,
    workspace_name: str,
) -> bytes:
    """One workbook holding the records, the statistics and the PRISMA flow."""
    book = Workbook()
    # A new workbook starts with one empty sheet; every sheet here is named.
    if (default := book.active) is not None:
        book.remove(default)
    o = statistics.overview

    _sheet(
        book,
        "Ringkasan",
        ["Metrik", "Nilai"],
        _pairs(
            [
                ("Workspace", workspace_name),
                ("Dokumen", o.documents),
                ("Sumber", o.sources),
                ("Penulis", o.authors),
                ("Dokumen penulis tunggal", o.single_authored),
                ("Periode", f"{o.year_min}\u2013{o.year_max}" if o.year_min else None),
                ("Pertumbuhan tahunan (%)", o.annual_growth_rate_pct),
                ("Total sitasi", o.total_citations),
                ("Rata-rata sitasi per dokumen", o.mean_citations),
                ("Rata-rata penulis per dokumen", o.mean_authors_per_document),
                ("Indeks kolaborasi", o.collaboration_index),
                ("Kolaborasi internasional (%)", o.international_coauthorship_pct),
                ("Kata kunci penulis", o.keywords_author),
                ("Kata kunci indeks", o.keywords_index),
                ("Referensi", o.references),
            ]
        ),
    )

    _sheet(
        book,
        "Produksi tahunan",
        ["Tahun", "Dokumen", "Rata-rata sitasi"],
        [[y.year, y.count, y.mean_citations] for y in o.documents_per_year],
    )

    rankings = [
        ("Sumber teratas", statistics.top_sources),
        ("Penulis teratas", statistics.top_authors),
        ("Afiliasi teratas", statistics.top_affiliations),
        ("Negara teratas", statistics.top_countries),
        ("Kata kunci teratas", statistics.top_keywords),
    ]
    for title, entities in rankings:
        _sheet(
            book,
            title,
            ["#", "Nama", "Dokumen", "Sitasi", "h-index", "g-index", "m-index", "Tahun pertama"],
            [
                [
                    i,
                    e.label,
                    e.documents,
                    e.citations,
                    e.h_index,
                    e.g_index,
                    e.m_index,
                    e.first_year,
                ]
                for i, e in enumerate(entities, start=1)
            ],
        )

    _sheet(
        book,
        "Hukum Lotka",
        ["Jumlah dokumen", "Penulis", "Proporsi teramati", "Proporsi model"],
        [
            [r.documents_written, r.authors, r.proportion, r.fitted_proportion]
            for r in statistics.lotka.rows
        ],
    )
    _sheet(
        book,
        "Hukum Bradford",
        ["#", "Sumber", "Dokumen", "Kumulatif", "Zona"],
        [[r.rank, r.label, r.documents, r.cumulative, r.zone] for r in statistics.bradford.rows],
    )

    reasons = prisma.automation_ineligible_by_reason
    _sheet(
        book,
        "PRISMA",
        ["Tahap", "Jumlah"],
        _pairs(
            [
                *[(f"Teridentifikasi: {s.label}", s.count) for s in prisma.identified_by_source],
                ("Total teridentifikasi", prisma.identified),
                ("Duplikat dihapus", prisma.duplicates_removed),
                ("Tidak layak (alat otomatis)", prisma.automation_ineligible),
                *[(f"  alasan: {reason.value}", count) for reason, count in reasons.items()],
                ("Disaring", prisma.screened),
                ("Menunggu tinjauan duplikat", prisma.pending_duplicate_reviews),
            ]
        ),
    )

    header = [label for _, label in RECORD_COLUMNS]
    keys = [key for key, _ in RECORD_COLUMNS]
    _sheet(
        book,
        "Rekaman",
        header,
        [[record_row(item).get(k) for k in keys] for item in kept],
    )
    if excluded:
        _sheet(
            book,
            "Tersaring",
            header,
            [[record_row(item, reason).get(k) for k in keys] for item, reason in excluded],
        )

    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()
