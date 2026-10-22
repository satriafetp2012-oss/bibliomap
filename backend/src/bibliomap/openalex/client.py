"""Async OpenAlex client with cursor paging and polite retries.

OpenAlex bills requests against a daily budget: requests without an API key
share one small budget per IP address, so a public deployment must configure
a key (or let users supply their own).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx

from bibliomap import __version__
from bibliomap.openalex.query import BASE_URL, PER_PAGE, SELECT_FIELDS, OpenAlexQuery, build_params

_RETRY_STATUS = {429, 500, 502, 503, 504}
# Retry-After above this means the daily budget is gone, not a brief throttle.
_MAX_RETRY_WAIT_S = 30.0


class OpenAlexError(RuntimeError):
    """Error with a user-facing (Indonesian) message."""


class OpenAlexBudgetError(OpenAlexError):
    pass


@dataclass
class FetchResult:
    works: list[dict[str, Any]]
    total_available: int
    cost_usd: float = 0.0
    truncated: bool = False


@dataclass
class OpenAlexClient:
    api_key: str | None = None
    mailto: str | None = None
    transport: httpx.AsyncBaseTransport | None = None
    base_url: str = BASE_URL
    timeout_s: float = 30.0
    max_retries: int = 3
    backoff_s: float = 1.0
    _cost_usd: float = field(default=0.0, init=False)

    def _credentials(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.api_key:
            params["api_key"] = self.api_key
        if self.mailto:
            params["mailto"] = self.mailto
        return params

    async def _get(self, client: httpx.AsyncClient, params: dict[str, str]) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            try:
                response = await client.get("/works", params=params | self._credentials())
            except httpx.TransportError as exc:
                if attempt == self.max_retries:
                    raise OpenAlexError("Tidak dapat terhubung ke OpenAlex.") from exc
                await asyncio.sleep(self.backoff_s * 2**attempt)
                continue

            self._cost_usd += float(response.headers.get("x-ratelimit-cost-usd", 0) or 0)
            if response.status_code == 200:
                data: dict[str, Any] = response.json()
                return data
            if response.status_code in _RETRY_STATUS and attempt < self.max_retries:
                wait = float(response.headers.get("retry-after", 0) or 0)
                if response.status_code == 429 and wait > _MAX_RETRY_WAIT_S:
                    break
                await asyncio.sleep(max(wait, self.backoff_s * 2**attempt))
                continue
            if response.status_code in (400, 403):
                raise OpenAlexError(f"OpenAlex menolak query: {_detail(response)}")
            if response.status_code != 429:
                raise OpenAlexError(f"OpenAlex error HTTP {response.status_code}.")
            break

        raise OpenAlexBudgetError(
            "Kuota harian OpenAlex habis. Masukkan API key OpenAlex Anda sendiri "
            "(gratis di openalex.org/settings/api) atau coba lagi besok."
        )

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            transport=self.transport,
            timeout=self.timeout_s,
            headers={"User-Agent": f"Bibliomap/{__version__}"},
        )

    async def count(self, query: OpenAlexQuery) -> int:
        async with self._client() as client:
            data = await self._get(client, build_params(query) | {"per_page": "1", "select": "id"})
        return int(data["meta"]["count"])

    async def fetch(self, query: OpenAlexQuery) -> FetchResult:
        """Fetch up to ``query.max_results`` works using cursor paging."""
        self._cost_usd = 0.0
        works: list[dict[str, Any]] = []
        total, cursor = 0, "*"
        params = build_params(query) | {"select": SELECT_FIELDS}

        async with self._client() as client:
            while cursor and len(works) < query.max_results:
                per_page = min(PER_PAGE, query.max_results - len(works))
                data = await self._get(
                    client, params | {"per_page": str(per_page), "cursor": cursor}
                )
                total = int(data["meta"]["count"])
                works.extend(data.get("results") or [])
                cursor = data["meta"].get("next_cursor")
                if not data.get("results"):
                    break

        return FetchResult(
            works=works[: query.max_results],
            total_available=total,
            cost_usd=round(self._cost_usd, 6),
            truncated=total > len(works),
        )


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    return str(body.get("message") or body.get("error") or body)[:200]
