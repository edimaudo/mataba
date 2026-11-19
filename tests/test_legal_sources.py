import httpx
import pytest
from fastapi import HTTPException

from app.services import legal_sources
from app.services.legal_sources import LawSource


def test_official_law_registry_covers_federal_provinces_and_territories():
    expected = {"CA", "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}
    assert set(legal_sources.LAW_SOURCES) == expected
    for source in legal_sources.LAW_SOURCES.values():
        assert source.official_url.startswith("https://")
        host = httpx.URL(source.official_url).host
        assert host
        assert any(marker in host for marker in (".gc.ca", ".gov.", ".ca", ".legis."))




def test_law_registry_marks_each_source_level_correctly():
    assert legal_sources.LAW_SOURCES["CA"].level == "federal"
    assert legal_sources.LAW_SOURCES["ON"].level == "provincial"
    assert legal_sources.LAW_SOURCES["NT"].level == "territorial"
    assert legal_sources.LAW_SOURCES["NU"].level == "territorial"
    assert legal_sources.LAW_SOURCES["YT"].level == "territorial"


def test_municipal_source_resolution_requires_an_explicit_curated_match(monkeypatch):
    parent = legal_sources.LAW_SOURCES["ON"]
    assert legal_sources._resolve_law_source("ON", municipality_name="Toronto", law_type="employment") == parent

    municipal = LawSource(
        code="ON-TORONTO-EMPLOYMENT",
        jurisdiction="City of Toronto",
        act_title="Test municipal employment bylaw",
        official_url="https://www.toronto.ca/test-law",
        level="municipal",
        parent_code="ON",
    )
    monkeypatch.setitem(
        legal_sources.MUNICIPAL_LAW_SOURCES,
        ("ON", "toronto", "employment"),
        municipal,
    )
    assert legal_sources._resolve_law_source("ON", municipality_name=" City of Toronto ", law_type="employment") == parent
    assert legal_sources._resolve_law_source("ON", municipality_name="Toronto", law_type="employment") == municipal
    # A configured registry key is normalized independently from the user-entered name.
    monkeypatch.setitem(
        legal_sources.MUNICIPAL_LAW_SOURCES,
        ("ON", "city-of-toronto", "employment"),
        municipal,
    )
    assert legal_sources._resolve_law_source("ON", municipality_name="City of Toronto", law_type="employment") == municipal


def test_municipal_registry_rejects_sources_with_wrong_parent(monkeypatch):
    invalid = LawSource(
        code="ON-TORONTO-EMPLOYMENT",
        jurisdiction="City of Toronto",
        act_title="Test municipal bylaw",
        official_url="https://www.toronto.ca/test-law",
        level="municipal",
        parent_code="QC",
    )
    monkeypatch.setitem(legal_sources.MUNICIPAL_LAW_SOURCES, ("ON", "toronto", "employment"), invalid)
    assert legal_sources._resolve_law_source("ON", municipality_name="Toronto") == legal_sources.LAW_SOURCES["ON"]




@pytest.mark.asyncio
async def test_retrieve_law_passages_uses_a_registered_municipal_official_source(monkeypatch):
    legal_sources._CACHE.clear()
    municipal = LawSource(
        code="ON-TORONTO-BUSINESS-LICENSING",
        jurisdiction="City of Toronto",
        act_title="Test Business Licensing Bylaw",
        official_url="https://www.toronto.ca/city-government/bylaws/",
        level="municipal",
        parent_code="ON",
    )
    monkeypatch.setitem(
        legal_sources.MUNICIPAL_LAW_SOURCES,
        ("ON", "toronto", "business_licensing"),
        municipal,
    )
    content = b"""<!doctype html><html><body>
    <p>A business licence is required for a person who operates a regulated business within the municipal boundaries.</p>
    </body></html>"""

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "www.toronto.ca"
        return httpx.Response(200, headers={"content-type": "text/html"}, content=content, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        source, passages = await legal_sources.retrieve_law_passages(
            "ON",
            "When is a business licence required?",
            municipality_name="Toronto",
            law_type="business_licensing",
            http_client=client,
        )

    assert source.level == "municipal"
    assert source.parent_code == "ON"
    assert source.jurisdiction == "City of Toronto"
    assert passages
    assert all(item.jurisdiction_code == "ON-TORONTO-BUSINESS-LICENSING" for item in passages)
    legal_sources._CACHE.clear()


@pytest.mark.asyncio
async def test_retrieve_law_passages_extracts_and_ranks_official_html():
    legal_sources._CACHE.clear()
    html = b"""<!doctype html><html><head><title>Act</title></head><body>
    <nav>Navigation unrelated links</nav>
    <h2>Overtime hours</h2>
    <p>An employer must pay overtime wages when an employee works more than the statutory threshold of hours in a work week.</p>
    <p>Vacation pay must be calculated using the employee's eligible wages under the applicable employment standards rules.</p>
    </body></html>"""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=html, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        source, passages = await legal_sources.retrieve_law_passages(
            "ON", "How must an employer pay overtime wages?", http_client=client
        )

    assert source.code == "ON"
    assert passages
    assert any("overtime wages" in passage.text.lower() for passage in passages)
    assert all(passage.official_url == source.official_url for passage in passages)


@pytest.mark.asyncio
async def test_law_retrieval_does_not_follow_redirects_outside_official_domain():
    legal_sources._CACHE.clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.ontario.ca":
            return httpx.Response(302, headers={"location": "https://attacker.example/law"}, request=request)
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<p>Some official law text with enough characters for extraction.</p>", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        with pytest.raises(HTTPException) as error:
            await legal_sources.retrieve_law_passages("ON", "employment standards", http_client=client)
    assert error.value.status_code == 502
    assert "redirected outside" in error.value.detail


@pytest.mark.asyncio
async def test_unknown_jurisdiction_is_rejected_without_fetching_a_url():
    with pytest.raises(HTTPException) as error:
        await legal_sources.retrieve_law_passages("ZZ", "employment standards")
    assert error.value.status_code == 422
