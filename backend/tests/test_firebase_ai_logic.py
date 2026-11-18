import json

import httpx
import pytest

from app.config import Settings
from app.services.firebase_ai_logic import (
    FirebaseAILogicError,
    generate_from_template,
)


def firebase_settings(**overrides):
    values = {
        "firebase_project_id": "mataba-test",
        "firebase_api_key": "test-web-api-key",
        "firebase_app_id": "1:123:web:abc",
        "firebase_ai_logic_location": "northamerica-northeast1",
        "firebase_ai_logic_model": "gemini-3.8-flash",
        "firebase_ai_logic_provisioned_throughput_enabled": True,
        "firebase_ai_analysis_template_id": "mataba-contract-analysis-v1",
        "firebase_ai_followup_template_id": "mataba-follow-up-v1",
        "require_app_check": True,
    }
    values.update(overrides)
    return Settings(**values)


async def fake_access_token():
    return "google-oauth-access-token"


@pytest.mark.asyncio
async def test_generate_uses_firebase_ai_logic_template_endpoint_and_adc_oauth():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": '{"executiveSummary":"Verified","findings":[]}'}]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_from_template(
            template_id="mataba-contract-analysis-v1",
            prompt="Use this sanitized contract text.",
            app_check_token="firebase-app-check-token",
            settings=firebase_settings(),
            http_client=client,
            access_token_provider=fake_access_token,
        )

    assert result == {"executiveSummary": "Verified", "findings": []}
    assert captured["url"] == (
        "https://firebasevertexai.googleapis.com/v1beta/projects/mataba-test/"
        "locations/northamerica-northeast1/templates/mataba-contract-analysis-v1:templateGenerateContent"
    )
    assert captured["headers"]["x-goog-api-key"] == "test-web-api-key"
    assert captured["headers"]["authorization"] == "Bearer google-oauth-access-token"
    assert captured["headers"]["x-firebase-appcheck"] == "firebase-app-check-token"
    assert captured["headers"]["x-firebase-appid"] == "1:123:web:abc"
    assert captured["body"] == {"inputs": {"prompt": "Use this sanitized contract text."}}


@pytest.mark.asyncio
async def test_generate_rejects_missing_app_check_before_network_call():
    async def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("No network call should be made without App Check")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FirebaseAILogicError, match="App Check token is required"):
            await generate_from_template(
                template_id="mataba-contract-analysis-v1",
                prompt="sanitized",
                app_check_token="",
                settings=firebase_settings(),
                http_client=client,
                access_token_provider=fake_access_token,
            )


@pytest.mark.asyncio
async def test_generate_returns_safe_error_for_missing_firebase_template():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"message": "internal details"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FirebaseAILogicError, match="template or model/location combination"):
            await generate_from_template(
                template_id="mataba-contract-analysis-v1",
                prompt="sanitized",
                app_check_token="firebase-app-check-token",
                settings=firebase_settings(),
                http_client=client,
                access_token_provider=fake_access_token,
            )


@pytest.mark.asyncio
async def test_gemini_3_8_montreal_is_blocked_without_provisioned_throughput():
    async def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("A non-supported region/model pair must never reach Firebase AI Logic")

    settings = firebase_settings(
        firebase_ai_logic_model="gemini-3.8-flash",
        firebase_ai_logic_provisioned_throughput_enabled=False,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FirebaseAILogicError, match="only with Provisioned Throughput"):
            await generate_from_template(
                template_id="mataba-contract-analysis-v1",
                prompt="sanitized",
                app_check_token="firebase-app-check-token",
                settings=settings,
                http_client=client,
                access_token_provider=fake_access_token,
            )


@pytest.mark.asyncio
async def test_gemini_3_8_montreal_is_allowed_only_when_provisioned_throughput_is_enabled():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": '{"answer":"supported"}'}]}}]},
        )

    settings = firebase_settings(
        firebase_ai_logic_model="gemini-3.8-flash",
        firebase_ai_logic_provisioned_throughput_enabled=True,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await generate_from_template(
            template_id="mataba-follow-up-v1",
            prompt="Use only the submitted sanitized evidence.",
            app_check_token="firebase-app-check-token",
            settings=settings,
            http_client=client,
            access_token_provider=fake_access_token,
        )

    assert result == {"answer": "supported"}
    assert "/locations/northamerica-northeast1/templates/" in captured["url"]


def test_ai_logic_configuration_block_uses_service_unavailable_status():
    from app.services.firebase_ai_logic import firebase_ai_logic_http_status
    assert firebase_ai_logic_http_status(FirebaseAILogicError("This model works only with Provisioned Throughput.")) == 503
    assert firebase_ai_logic_http_status(FirebaseAILogicError("Firebase AI Logic timed out.")) == 504
    assert firebase_ai_logic_http_status(FirebaseAILogicError("Firebase AI Logic returned HTTP 500.")) == 502
