import copy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from bibliomap.api.openalex import get_client_factory
from bibliomap.main import app
from bibliomap.openalex.client import OpenAlexBudgetError, OpenAlexClient, OpenAlexError
from bibliomap.openalex.mapper import reconstruct_abstract, work_to_record
from bibliomap.openalex.query import OpenAlexQuery, SearchScope, WorkType, build_params, public_url
from bibliomap.schema import DocumentType, SourceFormat

PAGE = json.loads((Path(__file__).parent / "fixtures" / "openalex_works_page.json").read_text())
WORKS = PAGE["results"]


# --- query builder --------------------------------------------------------


def test_build_params_title_abstract_with_all_filters():
    query = OpenAlexQuery(
        terms='motorcycle AND (helmet OR "head injury"), Indonesia',
        year_from=2015,
        year_to=2024,
        types=[WorkType.ARTICLE, WorkType.REVIEW],
        languages=["en", "id"],
        open_access_only=True,
    )
    params = build_params(query)

    assert "search" not in params
    assert params["filter"] == (
        'title_and_abstract.search:motorcycle AND (helmet OR "head injury")  Indonesia,'
        "publication_year:2015-2024,type:article|review,language:en|id,open_access.is_oa:true"
    )


def test_build_params_fulltext_and_open_year_ranges():
    assert build_params(OpenAlexQuery(terms="a, b", scope=SearchScope.FULLTEXT)) == {
        "search": "a, b"
    }
    assert build_params(OpenAlexQuery(terms="x", year_from=2020))["filter"].endswith(
        "publication_year:>2019"
    )
    assert build_params(OpenAlexQuery(terms="x", year_to=2010))["filter"].endswith(
        "publication_year:<2011"
    )


def test_public_url_is_readable_and_has_no_key():
    url = public_url(OpenAlexQuery(terms="helmet", year_from=2020, year_to=2021))
    assert url.startswith("https://api.openalex.org/works?filter=title_and_abstract.search:helmet,")
    assert "api_key" not in url


@pytest.mark.parametrize(
    "kwargs",
    [
        {"terms": ""},
        {"terms": "x", "year_from": 2024, "year_to": 2020},
        {"terms": "x", "languages": ["english"]},
        {"terms": "x", "max_results": 999_999},
    ],
)
def test_invalid_queries_rejected(kwargs):
    with pytest.raises(ValidationError):
        OpenAlexQuery(**kwargs)


# --- mapper ---------------------------------------------------------------


def test_reconstruct_abstract():
    assert reconstruct_abstract({"world": [1], "Hello": [0], "again": [3], "hello": [2]}) == (
        "Hello world hello again"
    )
    assert reconstruct_abstract(None) is None


def test_maps_real_work():
    work = WORKS[0]
    rec = work_to_record(work)

    assert rec is not None
    assert rec.source_format is SourceFormat.OPENALEX
    assert rec.source_id == "W3149448788"
    assert rec.doi == "10.1088/1757-899x/1098/6/062105"
    assert rec.year == 2021
    assert rec.document_type is DocumentType.CONFERENCE_PAPER
    assert rec.source_title == "IOP Conference Series Materials Science and Engineering"
    assert rec.issn == ["1757-8981", "1757-899X"]
    assert rec.publisher == "IOP Publishing"
    assert rec.abstract.startswith("Abstract Safety is an important thing")
    assert len(rec.authors) == len(work["authorships"])
    assert rec.authors[0].name == "Nadhifatul Maulidati"
    assert rec.authors[0].affiliations[0].startswith("Department of Mechanical Engineering")
    assert "Sampoerna University" in rec.affiliations
    assert rec.references and all(r.startswith("W") for r in rec.references)
    assert "helmet design" in rec.index_keywords


def test_maps_article_with_orcid_pmid_and_html_title():
    work = copy.deepcopy(WORKS[0])
    work.update(
        type="article",
        display_name="Helmets <i>save</i> lives",
        ids={"pmid": "https://pubmed.ncbi.nlm.nih.gov/33000001"},
        primary_location=None,
    )
    work["authorships"][0]["author"]["orcid"] = "https://orcid.org/0000-0002-1825-0097"
    rec = work_to_record(work)

    assert rec.title == "Helmets save lives"
    assert rec.document_type is DocumentType.ARTICLE
    assert rec.pmid == "33000001"
    assert rec.authors[0].orcid == "0000-0002-1825-0097"
    assert rec.source_title is None


def test_untitled_work_is_skipped():
    assert work_to_record({"id": "https://openalex.org/W1", "display_name": None}) is None


# --- client ---------------------------------------------------------------


def _paged_transport(seen: list[dict[str, list[str]]]) -> httpx.MockTransport:
    """Serve the fixture as two pages: 2 works, then 1."""

    def handler(request: httpx.Request) -> httpx.Response:
        params = parse_qs(urlsplit(str(request.url)).query)
        seen.append(params)
        first = params.get("cursor", ["*"]) == ["*"]
        body = {
            "meta": {"count": 3, "next_cursor": "page2" if first else None},
            "results": WORKS[:2] if first else WORKS[2:],
        }
        return httpx.Response(200, json=body, headers={"x-ratelimit-cost-usd": "0.001"})

    return httpx.MockTransport(handler)


async def test_fetch_pages_through_cursor_and_sends_credentials():
    seen: list[dict[str, list[str]]] = []
    client = OpenAlexClient(api_key="k123", mailto="a@b.c", transport=_paged_transport(seen))

    result = await client.fetch(OpenAlexQuery(terms="helmet"))

    assert len(result.works) == 3
    assert result.total_available == 3
    assert not result.truncated
    assert result.cost_usd == pytest.approx(0.002)
    assert [p["cursor"] for p in seen] == [["*"], ["page2"]]
    assert seen[0]["api_key"] == ["k123"] and seen[0]["mailto"] == ["a@b.c"]
    assert "abstract_inverted_index" in seen[0]["select"][0]


async def test_fetch_respects_max_results():
    seen: list[dict[str, list[str]]] = []
    client = OpenAlexClient(transport=_paged_transport(seen))

    result = await client.fetch(OpenAlexQuery(terms="helmet", max_results=2))

    assert len(result.works) == 2
    assert result.truncated
    assert len(seen) == 1 and seen[0]["per_page"] == ["2"]


async def test_retries_transient_errors():
    calls = iter([503, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        code = next(calls)
        body = {"meta": {"count": 65}, "results": []} if code == 200 else {}
        return httpx.Response(code, json=body)

    client = OpenAlexClient(transport=httpx.MockTransport(handler), backoff_s=0)
    assert await client.count(OpenAlexQuery(terms="helmet")) == 65


async def test_exhausted_budget_raises_budget_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={}, headers={"retry-after": "60000"})

    client = OpenAlexClient(transport=httpx.MockTransport(handler), backoff_s=0)
    with pytest.raises(OpenAlexBudgetError, match="API key"):
        await client.count(OpenAlexQuery(terms="helmet"))


async def test_bad_request_raises_with_detail():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "Invalid filter"})

    client = OpenAlexClient(transport=httpx.MockTransport(handler))
    with pytest.raises(OpenAlexError, match="Invalid filter"):
        await client.count(OpenAlexQuery(terms="helmet"))


# --- API ------------------------------------------------------------------


@pytest.fixture
def api():
    seen: list[dict[str, list[str]]] = []

    class MockedClient(OpenAlexClient):
        def __init__(self, **kwargs):
            super().__init__(transport=_paged_transport(seen), backoff_s=0, **kwargs)

    app.dependency_overrides[get_client_factory] = lambda: MockedClient
    yield TestClient(app), seen
    app.dependency_overrides.clear()


def test_count_endpoint(api):
    client, _ = api
    response = client.post("/api/openalex/count", json={"query": {"terms": "helmet"}})

    assert response.status_code == 200
    assert response.json()["count"] == 3
    assert "title_and_abstract.search:helmet" in response.json()["query_url"]


def test_import_endpoint_maps_records_and_prefers_user_key(api, monkeypatch):
    monkeypatch.setenv("BIBLIOMAP_OPENALEX_API_KEY", "server-key")
    client, seen = api
    response = client.post(
        "/api/openalex/import",
        json={"query": {"terms": "helmet", "max_results": 10}, "api_key": "user-key"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["record_count"] == 3
    assert body["result"]["source_format"] == "openalex"
    assert body["result"]["records"][0]["source_id"] == "W3149448788"
    assert seen[0]["api_key"] == ["user-key"]


def test_import_uses_server_key_when_user_has_none(api, monkeypatch):
    monkeypatch.setenv("BIBLIOMAP_OPENALEX_API_KEY", "server-key")
    client, seen = api
    client.post("/api/openalex/import", json={"query": {"terms": "helmet"}})
    assert seen[0]["api_key"] == ["server-key"]


def test_invalid_query_returns_422(api):
    client, _ = api
    response = client.post(
        "/api/openalex/count", json={"query": {"terms": "x", "year_from": 2024, "year_to": 2000}}
    )
    assert response.status_code == 422


def test_budget_error_maps_to_429():
    class BrokeClient(OpenAlexClient):
        def __init__(self, **kwargs):
            transport = httpx.MockTransport(
                lambda r: httpx.Response(429, json={}, headers={"retry-after": "60000"})
            )
            super().__init__(transport=transport, backoff_s=0, **kwargs)

    app.dependency_overrides[get_client_factory] = lambda: BrokeClient
    try:
        response = TestClient(app).post("/api/openalex/count", json={"query": {"terms": "x"}})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 429
    assert "Kuota harian" in response.json()["detail"]
