"""Download endpoints for maps, records and workbooks."""

from __future__ import annotations

import re
import zipfile
from datetime import UTC, datetime
from enum import StrEnum
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from bibliomap.api.analysis import NetworkOptions, ScienceMap, compute_map, compute_statistics
from bibliomap.api.workspaces import Cache, get_state
from bibliomap.exports import maps, workbook
from bibliomap.workspace.pipeline import WorkspaceState

router = APIRouter(prefix="/api/workspaces/{workspace_id}/exports", tags=["exports"])

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class MapFormat(StrEnum):
    VOSVIEWER = "vosviewer"
    GRAPHML = "graphml"
    PAJEK = "pajek"
    CSV = "csv"


class RecordFormat(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"


def _slug(name: str) -> str:
    cleaned = _UNSAFE.sub("-", name.strip()).strip("-").lower()
    return cleaned[:60] or "bibliomap"


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d")


def _attachment(content: bytes, filename: str, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        # The ASCII name is a fallback for clients that ignore filename*.
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"; '
            f"filename*=UTF-8''{filename}"
        },
    )


def _zip(members: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return buffer.getvalue()


async def _map_for(state: WorkspaceState, options: NetworkOptions) -> ScienceMap:
    records = {item.id: item.record for item in state.filtered.kept}
    return await run_in_threadpool(compute_map, records, options)


@router.post("/map")
async def export_map(
    workspace_id: str,
    options: NetworkOptions,
    cache: Cache,
    format: Annotated[MapFormat, Query(description="Format berkas peta.")] = MapFormat.VOSVIEWER,
) -> Response:
    state = get_state(cache, workspace_id)
    science_map = await _map_for(state, options)
    base = f"{_slug(state.workspace.name)}-{options.type.value}-{_stamp()}"

    match format:
        case MapFormat.VOSVIEWER:
            # VOSviewer reads a map file and a network file together, so the
            # pair ships as one archive with its cluster colours.
            members = {
                f"{base}-map.txt": maps.vosviewer_map(science_map),
                f"{base}-network.txt": maps.vosviewer_network(science_map),
                "cluster_colors.txt": maps.cluster_colors(science_map),
                "BACA-INI.txt": (
                    "Buka di VOSviewer: Create > Map based on network data?  Tidak.\n"
                    "Pilih 'Open' lalu 'VOSviewer map and network file', isi:\n"
                    f"  Map file     : {base}-map.txt\n"
                    f"  Network file : {base}-network.txt\n"
                    "Warna klaster: Options > Colors > Cluster colors > "
                    "Import, pilih cluster_colors.txt\n"
                ),
            }
            return _attachment(_zip(members), f"{base}-vosviewer.zip", "application/zip")
        case MapFormat.GRAPHML:
            return _attachment(
                maps.graphml(science_map).encode(), f"{base}.graphml", "application/xml"
            )
        case MapFormat.PAJEK:
            members = {
                f"{base}.net": maps.pajek_network(science_map),
                f"{base}.clu": maps.pajek_clusters(science_map),
            }
            return _attachment(_zip(members), f"{base}-pajek.zip", "application/zip")
        case MapFormat.CSV:
            members = {
                f"{base}-nodes.csv": maps.nodes_csv(science_map),
                f"{base}-edges.csv": maps.edges_csv(science_map),
            }
            return _attachment(_zip(members), f"{base}-csv.zip", "application/zip")


@router.get("/records")
async def export_records(
    workspace_id: str,
    cache: Cache,
    format: Annotated[RecordFormat, Query()] = RecordFormat.XLSX,
    include_excluded: Annotated[bool, Query(description="Sertakan rekaman tersaring.")] = False,
) -> Response:
    state = get_state(cache, workspace_id)
    base = f"{_slug(state.workspace.name)}-{_stamp()}"

    if format is RecordFormat.CSV:
        rows = [workbook.record_row(item) for item in state.filtered.kept]
        if include_excluded:
            rows += [workbook.record_row(item, reason) for item, reason in state.filtered.excluded]
        return _attachment(
            workbook.records_csv(rows).encode(), f"{base}-rekaman.csv", "text/csv; charset=utf-8"
        )

    records = {item.id: item.record for item in state.filtered.kept}
    statistics = await run_in_threadpool(compute_statistics, records, 50)
    content = await run_in_threadpool(
        workbook.build_workbook,
        kept=state.filtered.kept,
        excluded=state.filtered.excluded,
        statistics=statistics,
        prisma=state.prisma,
        workspace_name=state.workspace.name,
    )
    return _attachment(content, f"{base}-laporan.xlsx", XLSX_MEDIA_TYPE)
