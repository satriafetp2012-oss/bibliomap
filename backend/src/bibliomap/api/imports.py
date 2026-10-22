"""Stateless import preview: upload an export file, get canonical records back.

Persistent imports go through the workspace endpoints, which reuse
``parse_upload``.
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


UploadField = Annotated[UploadFile, File(description="File ekspor bibliografi.")]
FormatQuery = Annotated[SourceFormat | None, Query(description="Kosongkan untuk deteksi otomatis.")]


async def parse_upload(file: UploadFile, source_format: SourceFormat | None) -> ParseResult:
    """Validate size, then parse off the event loop."""
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
    return result


@router.post("/preview")
async def preview_import(file: UploadField, source_format: FormatQuery = None) -> ImportPreview:
    result = await parse_upload(file, source_format)
    return ImportPreview(filename=file.filename, record_count=len(result.records), result=result)
