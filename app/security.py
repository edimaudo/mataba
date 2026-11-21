"""Firebase Authentication and App Check verification for FastAPI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import hmac

import jwt
from fastapi import Header, HTTPException, Request, status
from starlette.concurrency import run_in_threadpool

from .config import get_settings
from .credentials import CredentialConfigurationError, load_service_account_info


@dataclass(frozen=True)
class Identity:
    uid: str
    email: str | None
    firebase_id_token: str
    app_check_token: str | None
    auth_time: int | None = None


def _firebase_sdk() -> tuple[Any, Any, Any, type[Exception]]:
    """Import Firebase Admin lazily so pure API logic and security tests remain importable."""
    try:
        import firebase_admin
        from firebase_admin import app_check, auth
        from firebase_admin.exceptions import FirebaseError
    except ImportError as exc:  # pragma: no cover - deployment packaging check
        raise HTTPException(
            status_code=503,
            detail="Firebase Admin SDK is not installed on the API service.",
        ) from exc
    return firebase_admin, auth, app_check, FirebaseError


def _firebase_app(firebase_admin: Any):
    settings = get_settings()
    if not settings.firebase_project_id:
        raise HTTPException(status_code=503, detail="Firebase project is not configured on the API.")
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    try:
        service_account_info = load_service_account_info(settings)
    except CredentialConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="The server Google service-account configuration is invalid.",
        ) from exc

    credential = None
    if service_account_info:
        from firebase_admin import credentials
        credential = credentials.Certificate(service_account_info)

    try:
        return firebase_admin.initialize_app(
            credential=credential,
            options={"projectId": settings.firebase_project_id},
        )
    except ValueError:
        # Another concurrent invocation may have initialized the default app.
        return firebase_admin.get_app()


async def require_identity(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    app_check_token: str | None = Header(default=None, alias="X-Firebase-AppCheck"),
) -> Identity:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A valid Firebase session is required.")

    token = authorization[7:].strip()
    if not token or len(token) > 8192:
        raise HTTPException(status_code=401, detail="Your Firebase session token is invalid. Refresh the app and try again.")

    settings = get_settings()
    firebase_admin, auth, app_check, FirebaseError = _firebase_sdk()
    firebase_app = _firebase_app(firebase_admin)

    try:
        decoded = await run_in_threadpool(
            auth.verify_id_token,
            token,
            app=firebase_app,
            check_revoked=settings.check_revoked_firebase_tokens,
        )
    except (ValueError, auth.InvalidIdTokenError, auth.ExpiredIdTokenError,
            auth.RevokedIdTokenError, auth.UserDisabledError) as exc:
        raise HTTPException(status_code=401, detail="Your Firebase session has expired. Refresh the app and try again.") from exc
    except FirebaseError as exc:
        raise HTTPException(status_code=503, detail="Firebase authentication could not be verified.") from exc

    uid = decoded.get("uid") if isinstance(decoded, dict) else None
    if not isinstance(uid, str) or not uid:
        raise HTTPException(status_code=401, detail="Your Firebase session token is invalid. Refresh the app and try again.")

    if settings.require_app_check:
        if not app_check_token:
            raise HTTPException(status_code=401, detail="Firebase App Check token is required.")
        if len(app_check_token) > 8192:
            raise HTTPException(status_code=401, detail="Firebase App Check verification failed.")
        if not settings.firebase_app_id:
            raise HTTPException(status_code=503, detail="Firebase App ID is not configured for App Check verification.")
        try:
            claims = await run_in_threadpool(app_check.verify_token, app_check_token)
        except (ValueError, jwt.InvalidTokenError) as exc:
            raise HTTPException(status_code=401, detail="Firebase App Check verification failed.") from exc
        except jwt.PyJWKClientError as exc:
            raise HTTPException(status_code=503, detail="Firebase App Check could not retrieve its verification keys.") from exc
        except FirebaseError as exc:
            raise HTTPException(status_code=503, detail="Firebase App Check could not be verified.") from exc

        # A valid token from another web app in the same Firebase project is
        # not accepted by this API. The configured App ID is the allow-list.
        token_app_id = claims.get("app_id") or claims.get("sub") if isinstance(claims, dict) else None
        if not isinstance(token_app_id, str) or not hmac.compare_digest(token_app_id, settings.firebase_app_id):
            raise HTTPException(status_code=401, detail="Firebase App Check token belongs to an unapproved application.")

    return Identity(
        uid=uid,
        email=decoded.get("email"),
        firebase_id_token=token,
        app_check_token=app_check_token,
        auth_time=decoded.get("auth_time"),
    )
