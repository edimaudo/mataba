import json

import httpx
import pytest
from fastapi import HTTPException

from app import main
from app.security import Identity, require_identity


@pytest.mark.asyncio
async def test_health_is_minimal_and_has_security_headers():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'service': 'mataba-api'}
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['referrer-policy'] == 'no-referrer'
    assert 'project' not in response.text.lower()
    assert 'template' not in response.text.lower()


@pytest.mark.asyncio
async def test_analysis_rejects_residual_pii_before_calling_firebase_ai_logic(monkeypatch):
    async def should_not_run(**_kwargs):
        raise AssertionError('Firebase AI Logic must not receive residual PII')

    monkeypatch.setattr(main, 'generate_from_template', should_not_run)
    main.app.dependency_overrides[require_identity] = lambda: Identity(
        uid='security-test-user', email='user@example.ca',
        firebase_id_token='verified-id-token', app_check_token='verified-app-check',
    )
    payload = {
        'contractType': 'Employment Agreement',
        'language': 'en',
        'privacyConfirmed': True,
        'contractPages': [{
            'sourceId': 'contract-page-1', 'documentName': 'Employment Offer',
            'sourceType': 'CONTRACT', 'pageNumber': 1,
            'text': 'Contact the employee at jane.doe@example.ca about the probation terms.',
        }],
        'referencePages': [],
    }
    try:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            response = await client.post('/api/analyze', json=payload)
        assert response.status_code == 422
        assert 'personal identifiers' in response.json()['detail']
        assert 'jane.doe@example.ca' not in response.text
    finally:
        main.app.dependency_overrides.pop(require_identity, None)


@pytest.mark.asyncio
async def test_analysis_request_body_limit_rejects_oversized_payload():
    # Exercise the configured middleware threshold without relying on mutable
    # settings after the ASGI middleware stack has already been constructed.
    oversized = b'{' + (b' ' * (main.settings.max_api_request_bytes + 1))
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.post('/api/analyze', content=oversized)
    assert response.status_code == 413
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.asyncio
async def test_analysis_requires_identity_before_processing(monkeypatch):
    async def should_not_run(**_kwargs):
        raise AssertionError('Analysis must not run without verified Firebase identity')

    monkeypatch.setattr(main, 'generate_from_template', should_not_run)
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.post('/api/analyze', json={
            'contractType': 'General', 'language': 'en', 'privacyConfirmed': True,
            'contractPages': [{
                'sourceId': 'p1', 'documentName': 'Contract', 'sourceType': 'CONTRACT',
                'pageNumber': 1, 'text': 'The parties agree to the following contract terms.',
            }],
            'referencePages': [],
        })
    assert response.status_code == 401


def test_firestore_rules_restrict_access_to_owned_supported_collections():
    from pathlib import Path
    rules = (Path(__file__).resolve().parents[1] / 'firebase' / 'firestore.rules').read_text()
    assert "collectionName in ['reviews', 'references', 'folders']" in rules
    assert 'request.auth.uid == userId' in rules
    assert 'request.resource.data.userId == userId' in rules
    assert 'allow get, list, create, update: if false;' in rules


def test_storage_rules_do_not_allow_client_uploads():
    from pathlib import Path
    rules = (Path(__file__).resolve().parents[1] / 'firebase' / 'storage.rules').read_text()
    assert 'allow get, list, delete:' in rules
    assert 'allow create, update: if false;' in rules
    assert 'request.auth.uid == userId' in rules


@pytest.mark.asyncio
async def test_cors_allows_configured_origin_and_rejects_unlisted_origin():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        allowed = await client.options(
            '/api/analyze',
            headers={
                'Origin': 'http://localhost:4173',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'authorization,content-type,x-firebase-appcheck',
            },
        )
        denied = await client.options(
            '/api/analyze',
            headers={
                'Origin': 'https://untrusted.example',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'authorization,content-type,x-firebase-appcheck',
            },
        )
    assert allowed.headers.get('access-control-allow-origin') == 'http://localhost:4173'
    assert denied.headers.get('access-control-allow-origin') is None
