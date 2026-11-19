import httpx
import pytest
from fastapi.testclient import TestClient

from app import main
from app.schemas import LegalQADraft, LegalQACitationDraft
from app.security import Identity, require_identity
from app.services.legal_sources import LAW_SOURCES, LawPassage


@pytest.fixture
def signed_in_user():
    main.app.dependency_overrides[require_identity] = lambda: Identity(
        uid="legal-qa-integration-user",
        email="qa-user@example.ca",
        firebase_id_token="verified-firebase-id-token",
        app_check_token="verified-app-check-token",
    )
    yield
    main.app.dependency_overrides.pop(require_identity, None)


@pytest.mark.asyncio
async def test_standalone_legal_qa_works_without_contract_or_document_fields(monkeypatch, signed_in_user):
    source = LAW_SOURCES["ON"]
    passage = LawPassage(
        source_id="law-on-1", jurisdiction_code="ON", jurisdiction=source.jurisdiction,
        act_title=source.act_title, official_url=source.official_url,
        section_label="Section 22", page_number=None,
        text="An employer must pay overtime wages when an employee works more than the statutory threshold of hours in a work week.",
    )
    captured = {}

    async def fake_retrieve(jurisdiction_code: str, question: str, *, municipality_name=None, law_type="employment"):
        captured["jurisdiction"] = jurisdiction_code
        captured["question"] = question
        captured["municipality_name"] = municipality_name
        captured["law_type"] = law_type
        return source, [passage]

    async def fake_generate(**kwargs):
        captured.update(kwargs)
        return LegalQADraft(
            answer="The Act requires overtime wages after the applicable threshold.",
            citations=[LegalQACitationDraft(sourceId=passage.source_id, excerpt=passage.text)],
        ).model_dump()

    monkeypatch.setattr(main, "retrieve_law_passages", fake_retrieve)
    monkeypatch.setattr(main, "generate_from_template", fake_generate)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post("/api/legal-qa", json={
            "question": "How does overtime work in Ontario?",
            "jurisdictionCode": "ON",
            "language": "en",
        })

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evidenceFound"] is True
    assert body["jurisdictionCode"] == "ON"
    assert body["citations"][0]["verified"] is True
    assert captured["template_id"] == main.settings.firebase_ai_legal_qa_template_id
    assert captured["jurisdiction"] == "ON"
    assert captured["municipality_name"] is None
    assert captured["law_type"] == "employment"
    assert body["jurisdictionLevel"] == "provincial"
    assert body["sourceLevel"] == "provincial"
    assert "contractPages" not in response.json()
    assert "pages" not in response.json()




@pytest.mark.asyncio
async def test_municipal_context_is_carried_to_retrieval_prompt_and_response(monkeypatch, signed_in_user):
    source = LAW_SOURCES["ON"]
    passage = LawPassage(
        source_id="law-on-municipal-context-1", jurisdiction_code="ON", jurisdiction=source.jurisdiction,
        act_title=source.act_title, official_url=source.official_url,
        section_label="Section 22", page_number=None,
        text="An employer must pay overtime wages when an employee works more than the statutory threshold of hours in a work week.",
    )
    captured = {}

    async def fake_retrieve(jurisdiction_code: str, question: str, *, municipality_name=None, law_type="employment"):
        captured["jurisdiction"] = jurisdiction_code
        captured["municipality_name"] = municipality_name
        captured["law_type"] = law_type
        return source, [passage]

    async def fake_generate(**kwargs):
        captured["prompt"] = kwargs["prompt"]
        return LegalQADraft(
            answer="The provincial statute is the only source supplied for this municipal context.",
            citations=[LegalQACitationDraft(sourceId=passage.source_id, excerpt=passage.text)],
        ).model_dump()

    monkeypatch.setattr(main, "retrieve_law_passages", fake_retrieve)
    monkeypatch.setattr(main, "generate_from_template", fake_generate)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post("/api/legal-qa", json={
            "question": "Does a Toronto bylaw change employment standards?",
            "lawType": "employment",
            "jurisdictionCode": "ON",
            "jurisdictionLevel": "municipal",
            "municipalityName": "Toronto",
            "language": "en",
        })

    assert response.status_code == 200, response.text
    body = response.json()
    assert captured["jurisdiction"] == "ON"
    assert captured["municipality_name"] == "Toronto"
    assert captured["law_type"] == "employment"
    assert "Requested municipality: Toronto" in captured["prompt"]
    assert "no matching official municipal source was retrieved" in captured["prompt"]
    assert body["jurisdictionLevel"] == "municipal"
    assert body["municipalityName"] == "Toronto"
    assert body["sourceLevel"] == "provincial"
    assert body["jurisdictionCode"] == "ON"


@pytest.mark.asyncio
async def test_standalone_legal_qa_requires_firebase_identity():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post("/api/legal-qa", json={
            "question": "How does overtime work in Ontario?",
            "jurisdictionCode": "ON",
            "language": "en",
        })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_standalone_legal_qa_blocks_residual_personal_information(monkeypatch, signed_in_user):
    async def should_not_retrieve(*_args, **_kwargs):
        raise AssertionError("Legal Q&A retrieval must not receive a question with residual PII")

    monkeypatch.setattr(main, "retrieve_law_passages", should_not_retrieve)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.post("/api/legal-qa", json={
            "question": "Does Jane Smith jane.smith@example.ca qualify for overtime?",
            "jurisdictionCode": "ON",
            "language": "en",
        })
    assert response.status_code == 422
    assert "jane.smith@example.ca" not in response.text


def test_jurisdiction_catalog_requires_identity():
    with TestClient(main.app) as client:
        response = client.get("/api/legal-qa/jurisdictions")
    assert response.status_code == 401
