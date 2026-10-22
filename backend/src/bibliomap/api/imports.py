"""Import endpoint: upload an export file and get canonical records back.

Phase 1 is stateless: records are parsed and returned for preview. Persisting
them into a project arrives with the database layer.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from bibliomap.parsers import UnknownFormatError, parse_bytes
from bibliomap.schema import ParseResult, SourceFormat

router = APIRouter(prefix="/api/imports", tags=["imports"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class ImportPreview(BaseModel):
    filename: str | None
    record_count: int
    result: ParseResult


@router.post("/preview")
async def preview_import(
    file: Annotated[UploadFile, File(description="Ekspor WoS, Scopus, RIS, atau PubMed.")],
    source_format: Annotated[
        SourceFormat | None, Query(description="Kosongkan untuk deteksi otomatis.")
    ] = None,
) -> ImportPreview:
    # Read one byte past the limit so oversized files are rejected without
    # loading arbitrarily large bodies into memory.
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Ukuran file melebihi batas 50 MB.")
    if not data.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "File kosong.")

    try:
        # Parsing is CPU-bound; keep the event loop free.
        result = await run_in_threadpool(parse_bytes, data, source_format)
    except UnknownFormatError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    return ImportPreview(filename=file.filename, record_count=len(result.records), result=result)
