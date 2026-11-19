from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import security
from app.config import Settings


class FakeFirebaseError(Exception):
    pass


class InvalidIdTokenError(Exception):
    pass


class ExpiredIdTokenError(InvalidIdTokenError):
    pass


class RevokedIdTokenError(InvalidIdTokenError):
    pass


class UserDisabledError(Exception):
    pass


class FakeAuth:
    def __init__(self, decoded=None, error=None):
        self.decoded = decoded or {"uid": "user-1", "email": "user@example.ca", "auth_time": 1234}
        self.error = error
        self.calls = []
        self.InvalidIdTokenError = InvalidIdTokenError
        self.ExpiredIdTokenError = ExpiredIdTokenError
        self.RevokedIdTokenError = RevokedIdTokenError
        self.UserDisabledError = UserDisabledError

    def verify_id_token(self, token, **kwargs):
        self.calls.append((token, kwargs))
        if self.error:
            raise self.error
        return self.decoded


class FakeAppCheck:
    def __init__(self, claims=None, error=None):
        self.claims = claims or {"sub": "1:123:web:mataba", "aud": ["123", "mataba-test"]}
        self.error = error
        self.calls = []

    def verify_token(self, token):
        self.calls.append(token)
        if self.error:
            raise self.error
        return self.claims


def fake_request(path="/api/analyze"):
    return Request({"type": "http", "method": "POST", "path": path,
                    "headers": [], "query_string": b"", "server": ("test", 80),
                    "client": ("test", 123), "scheme": "http"})


def patch_security(monkeypatch, auth=None, app_check=None, settings=None):
    auth = auth or FakeAuth()
    app_check = app_check or FakeAppCheck()
    sdk = SimpleNamespace(get_app=lambda: object(), initialize_app=lambda **_: object())
    monkeypatch.setattr(security, "_firebase_sdk", lambda: (sdk, auth, app_check, FakeFirebaseError))
    monkeypatch.setattr(security, "_firebase_app", lambda _sdk: object())
    monkeypatch.setattr(security, "get_settings", lambda: settings or Settings(
        firebase_project_id="mataba-test", firebase_app_id="1:123:web:mataba",
        require_app_check=True, check_revoked_firebase_tokens=True,
    ))
    return auth, app_check


@pytest.mark.asyncio
async def test_identity_requires_bearer_token(monkeypatch):
    patch_security(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await security.require_identity(fake_request(), None, "app-token")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_identity_rejects_empty_or_oversized_id_token(monkeypatch):
    patch_security(monkeypatch)
    for token in ("Bearer ", "Bearer " + "a" * 8193):
        with pytest.raises(HTTPException) as exc:
            await security.require_identity(fake_request(), token, "app-token")
        assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_identity_verifies_id_token_and_app_check_and_binds_app_id(monkeypatch):
    auth, app_check = patch_security(monkeypatch)
    result = await security.require_identity(fake_request(), "Bearer signed-id-token", "signed-app-check-token")
    assert result.uid == "user-1"
    assert result.email == "user@example.ca"
    assert result.auth_time == 1234
    assert auth.calls[0][0] == "signed-id-token"
    assert auth.calls[0][1]["check_revoked"] is True
    assert app_check.calls == ["signed-app-check-token"]


@pytest.mark.asyncio
async def test_identity_rejects_app_check_token_for_another_web_app(monkeypatch):
    _, app_check = patch_security(monkeypatch, app_check=FakeAppCheck({"sub": "1:123:web:other-app"}))
    with pytest.raises(HTTPException) as exc:
        await security.require_identity(fake_request(), "Bearer good-id", "valid-but-other-app")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_invalid_firebase_id_token_is_401(monkeypatch):
    patch_security(monkeypatch, auth=FakeAuth(error=ExpiredIdTokenError("expired")))
    with pytest.raises(HTTPException) as exc:
        await security.require_identity(fake_request(), "Bearer expired", "app-token")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_app_check_missing_is_401_and_missing_app_id_configuration_is_503(monkeypatch):
    patch_security(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await security.require_identity(fake_request(), "Bearer id-token", None)
    assert exc.value.status_code == 401

    patch_security(monkeypatch, settings=Settings(firebase_project_id="mataba-test", firebase_app_id="", require_app_check=True))
    with pytest.raises(HTTPException) as exc:
        await security.require_identity(fake_request(), "Bearer id-token", "app-token")
    assert exc.value.status_code == 503
