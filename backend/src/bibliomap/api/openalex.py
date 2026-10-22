"""OpenAlex search endpoints: count matches, then import them as records."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from bibliomap.config import Settings, get_settings
from bibliomap.openalex.client import OpenAlexBudgetError, OpenAlexClient, OpenAlexError
from bibliomap.openalex.mapper import work_to_record
from bibliomap.openalex.query import OpenAlexQuery, public_url
from bibliomap.schema import ParseResult, ParseWarning, Record, SourceFormat

router = APIRouter(prefix="/api/openalex", tags=["openalex"])


class OpenAlexRequest(BaseModel):
    query: OpenAlexQuery
    # A user's own key (BYO) takes precedence over the server key. It is used
    # for this request only and never stored or logged.
    api_key: str | None = Field(default=None, max_length=200, repr=False)


class CountResponse(BaseModel):
    count: int
    query_url: str


class OpenAlexImport(BaseModel):
    record_count: int
    total_available: int
    truncated: bool
    cost_usd: float
    query_url: str
    result: ParseResult


def get_client_factory() -> type[OpenAlexClient]:
    """Indirection so tests can inject a client with a mock transport."""
    return OpenAlexClient


ClientFactory = Annotated[type[OpenAlexClient], Depends(get_client_factory)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _client(request: OpenAlexRequest, factory: type[OpenAlexClient], s: Settings) -> OpenAlexClient:
    return factory(api_key=request.api_key or s.openalex_api_key, mailto=s.openalex_mailto)


def _http_error(exc: OpenAlexError) -> HTTPException:
    code = (
        status.HTTP_429_TOO_MANY_REQUESTS
        if isinstance(exc, OpenAlexBudgetError)
        else status.HTTP_502_BAD_GATEWAY
    )
    return HTTPException(code, str(exc))


@router.post("/count")
async def count_works(
    request: OpenAlexRequest, factory: ClientFactory, settings: AppSettings
) -> CountResponse:
    try:
        count = await _client(request, factory, settings).count(request.query)
    except OpenAlexError as exc:
        raise _http_error(exc) from exc
    return CountResponse(count=count, query_url=public_url(request.query))


async def run_openalex_import(
    request: OpenAlexRequest, factory: type[OpenAlexClient], settings: Settings
) -> OpenAlexImport:
    """Fetch and map works; shared by the preview and workspace endpoints."""
    try:
        fetched = await _client(request, factory, settings).fetch(request.query)
    except OpenAlexError as exc:
        raise _http_error(exc) from exc

    records: list[Record] = []
    warnings: list[ParseWarning] = []
    for index, work in enumerate(fetched.works):
        record = work_to_record(work)
        if record is None:
            warnings.append(ParseWarning(record_index=index, message="Karya tanpa judul."))
        else:
            records.append(record)

    return OpenAlexImport(
        record_count=len(records),
        total_available=fetched.total_available,
        truncated=fetched.truncated,
        cost_usd=fetched.cost_usd,
        query_url=public_url(request.query),
        result=ParseResult(source_format=SourceFormat.OPENALEX, records=records, warnings=warnings),
    )


@router.post("/import")
async def import_works(
    request: OpenAlexRequest, factory: ClientFactory, settings: AppSettings
) -> OpenAlexImport:
    return await run_openalex_import(request, factory, settings)
