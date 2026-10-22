"""Workspace endpoints: imports, duplicate review, filters and PRISMA."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from bibliomap.api.imports import FormatQuery, UploadField, parse_upload
from bibliomap.api.openalex import AppSettings, ClientFactory, OpenAlexRequest, run_openalex_import
from bibliomap.schema import DocumentType, SourceFormat
from bibliomap.workspace.dedup import CandidatePair
from bibliomap.workspace.filters import ExclusionReason, FilterSpec
from bibliomap.workspace.merge import MergedRecord
from bibliomap.workspace.pipeline import StateCache, WorkspaceState
from bibliomap.workspace.prisma import PrismaFlow
from bibliomap.workspace.store import ImportInfo, Workspace, WorkspaceNotFoundError, WorkspaceStore

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

_ABSTRACT_PREVIEW_CHARS = 400


@lru_cache
def get_store() -> WorkspaceStore:
    return WorkspaceStore(os.environ.get("BIBLIOMAP_DB_PATH", "data/bibliomap.sqlite3"))


@lru_cache
def get_cache() -> StateCache:
    return StateCache(get_store())


Store = Annotated[WorkspaceStore, Depends(get_store)]
Cache = Annotated[StateCache, Depends(get_cache)]


# --- response models ------------------------------------------------------


class CreateWorkspace(BaseModel):
    name: str = Field(default="Workspace baru", min_length=1, max_length=200)


class WorkspaceCounts(BaseModel):
    identified: int
    unique: int
    duplicates_removed: int
    pending_reviews: int
    kept: int
    excluded: int


class WorkspaceSummary(BaseModel):
    workspace: Workspace
    imports: list[ImportInfo]
    counts: WorkspaceCounts


class RecordView(BaseModel):
    """Compact record for side-by-side duplicate review."""

    id: int
    import_label: str
    source_format: SourceFormat
    title: str
    authors: list[str]
    author_count: int
    year: int | None
    source_title: str | None
    document_type: DocumentType
    doi: str | None
    volume: str | None
    issue: str | None
    pages: str | None
    abstract: str | None


class PendingPair(BaseModel):
    a: RecordView
    b: RecordView
    title_similarity: int
    reasons: list[str]


class PendingPage(BaseModel):
    total: int
    items: list[PendingPair]


class Decision(BaseModel):
    record_a: int
    record_b: int
    same: bool


class RenameImport(BaseModel):
    label: str = Field(min_length=1, max_length=200)


class RecordRow(BaseModel):
    merged: MergedRecord
    exclusion_reason: ExclusionReason | None = None


class RecordPage(BaseModel):
    total: int
    items: list[RecordRow]


# --- helpers --------------------------------------------------------------


def _state(cache: StateCache, workspace_id: str) -> WorkspaceState:
    try:
        return cache.get(workspace_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace tidak ditemukan.") from exc


def _require_workspace(store: WorkspaceStore, workspace_id: str) -> None:
    try:
        store.get_workspace(workspace_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace tidak ditemukan.") from exc


def _summary(state: WorkspaceState) -> WorkspaceSummary:
    return WorkspaceSummary(
        workspace=state.workspace,
        imports=state.imports,
        counts=WorkspaceCounts(
            identified=state.prisma.identified,
            unique=len(state.merged),
            duplicates_removed=state.dedup.duplicates_removed,
            pending_reviews=len(state.dedup.pending),
            kept=len(state.filtered.kept),
            excluded=len(state.filtered.excluded),
        ),
    )


def _view(state: WorkspaceState, record_id: int) -> RecordView:
    stored = state.records[record_id]
    rec = stored.record
    labels = {imp.id: imp.label for imp in state.imports}
    pages = "-".join(p for p in (rec.page_start, rec.page_end) if p) or rec.article_number
    abstract = rec.abstract
    if abstract and len(abstract) > _ABSTRACT_PREVIEW_CHARS:
        abstract = abstract[:_ABSTRACT_PREVIEW_CHARS].rsplit(" ", 1)[0] + " …"
    return RecordView(
        id=stored.id,
        import_label=labels.get(stored.import_id, "?"),
        source_format=rec.source_format,
        title=rec.title,
        authors=[a.name for a in rec.authors[:5]],
        author_count=len(rec.authors),
        year=rec.year,
        source_title=rec.source_title,
        document_type=rec.document_type,
        doi=rec.doi,
        volume=rec.volume,
        issue=rec.issue,
        pages=pages,
        abstract=abstract,
    )


def _pending_pair(state: WorkspaceState, pair: CandidatePair) -> PendingPair:
    return PendingPair(
        a=_view(state, pair.a),
        b=_view(state, pair.b),
        title_similarity=pair.title_similarity,
        reasons=list(pair.reasons),
    )


# --- endpoints ------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
def create_workspace(body: CreateWorkspace, store: Store) -> Workspace:
    return store.create_workspace(body.name)


@router.get("/{workspace_id}")
def get_workspace(workspace_id: str, cache: Cache) -> WorkspaceSummary:
    return _summary(_state(cache, workspace_id))


@router.post("/{workspace_id}/imports/file", status_code=status.HTTP_201_CREATED)
async def import_file(
    workspace_id: str, file: UploadField, store: Store, source_format: FormatQuery = None
) -> ImportInfo:
    _require_workspace(store, workspace_id)
    result = await parse_upload(file, source_format)
    if not result.records:
        detail = result.warnings[0].message if result.warnings else "Tidak ada rekaman terbaca."
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)
    return await run_in_threadpool(
        lambda: store.add_import(
            workspace_id,
            source_format=result.source_format,
            records=result.records,
            warnings=result.warnings,
            origin=file.filename,
        )
    )


@router.post("/{workspace_id}/imports/openalex", status_code=status.HTTP_201_CREATED)
async def import_openalex(
    workspace_id: str,
    request: OpenAlexRequest,
    store: Store,
    factory: ClientFactory,
    settings: AppSettings,
) -> ImportInfo:
    _require_workspace(store, workspace_id)
    fetched = await run_openalex_import(request, factory, settings)
    # The query URL is the reproducible description of this import.
    return await run_in_threadpool(
        lambda: store.add_import(
            workspace_id,
            source_format=SourceFormat.OPENALEX,
            records=fetched.result.records,
            warnings=fetched.result.warnings,
            origin=fetched.query_url,
        )
    )


@router.patch("/{workspace_id}/imports/{import_id}")
def rename_import(workspace_id: str, import_id: int, body: RenameImport, store: Store) -> None:
    _require_workspace(store, workspace_id)
    store.rename_import(workspace_id, import_id, body.label)


@router.delete("/{workspace_id}/imports/{import_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_import(workspace_id: str, import_id: int, store: Store) -> None:
    _require_workspace(store, workspace_id)
    if not store.delete_import(workspace_id, import_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Impor tidak ditemukan.")


@router.get("/{workspace_id}/dedup/pending")
def pending_duplicates(
    workspace_id: str,
    cache: Cache,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PendingPage:
    state = _state(cache, workspace_id)
    page = state.dedup.pending[offset : offset + limit]
    return PendingPage(
        total=len(state.dedup.pending), items=[_pending_pair(state, p) for p in page]
    )


@router.post("/{workspace_id}/dedup/decisions", status_code=status.HTTP_204_NO_CONTENT)
def decide_duplicate(workspace_id: str, body: Decision, store: Store, cache: Cache) -> None:
    state = _state(cache, workspace_id)
    if body.record_a not in state.records or body.record_b not in state.records:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rekaman tidak ditemukan.")
    if body.record_a == body.record_b:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pilih dua rekaman berbeda.")
    store.set_decision(workspace_id, body.record_a, body.record_b, body.same)


@router.delete("/{workspace_id}/dedup/decisions", status_code=status.HTTP_204_NO_CONTENT)
def undo_decision(workspace_id: str, record_a: int, record_b: int, store: Store) -> None:
    _require_workspace(store, workspace_id)
    store.delete_decision(workspace_id, record_a, record_b)


@router.put("/{workspace_id}/filters")
def set_filters(
    workspace_id: str, spec: FilterSpec, store: Store, cache: Cache
) -> WorkspaceSummary:
    _require_workspace(store, workspace_id)
    store.set_filters(workspace_id, spec)
    return _summary(_state(cache, workspace_id))


@router.get("/{workspace_id}/records")
def list_records(
    workspace_id: str,
    cache: Cache,
    status_: Annotated[Literal["kept", "excluded"], Query(alias="status")] = "kept",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> RecordPage:
    state = _state(cache, workspace_id)
    rows = (
        [RecordRow(merged=m) for m in state.filtered.kept]
        if status_ == "kept"
        else [RecordRow(merged=m, exclusion_reason=r) for m, r in state.filtered.excluded]
    )
    return RecordPage(total=len(rows), items=rows[offset : offset + limit])


@router.get("/{workspace_id}/prisma")
def prisma(workspace_id: str, cache: Cache) -> PrismaFlow:
    return _state(cache, workspace_id).prisma
