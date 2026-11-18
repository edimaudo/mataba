"""Server-side Firebase AI Logic prompt-template calls.

FastAPI verifies the end-user Firebase ID token and App Check token. The
server-to-server Firebase AI Logic REST request is separately authenticated
with Application Default Credentials (OAuth cloud-platform scope), as required
by Google's REST reference. No Google Gen AI or model-specific SDK is used.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable, Awaitable

import httpx

from ..config import Settings, get_settings


class FirebaseAILogicError(RuntimeError):
    """Safe error raised for failed Firebase AI Logic calls."""


# Gemini 3.8 Flash supports in-region processing in Montréal only with
# Provisioned Throughput. Standard PayGo is listed only for global/us/eu.
# Keep Montréal blocked unless the operator explicitly confirms the project
# has Provisioned Throughput configured for this model and region.
MODEL_PAYGO_LOCATIONS: dict[str, set[str]] = {
    "gemini-3.8-flash": {"global", "us", "eu"},
}
MODEL_PROVISIONED_THROUGHPUT_LOCATIONS: dict[str, set[str]] = {
    "gemini-3.8-flash": {"northamerica-northeast1"},
}


def validate_model_location(
    model: str,
    location: str,
    provisioned_throughput_enabled: bool = False,
) -> None:
    if location in MODEL_PAYGO_LOCATIONS.get(model, set()):
        return
    if location in MODEL_PROVISIONED_THROUGHPUT_LOCATIONS.get(model, set()):
        if provisioned_throughput_enabled:
            return
        raise FirebaseAILogicError(
            f"Firebase AI Logic model '{model}' supports in-region processing in '{location}' "
            "only with Provisioned Throughput. Enable and verify Provisioned Throughput for "
            "the Firebase/Agent Platform project before allowing contract analysis."
        )
    raise FirebaseAILogicError(
        f"Firebase AI Logic model '{model}' is not documented for location '{location}' "
        "with the configured consumption mode. Cloud analysis is blocked rather than "
        "silently switching regions."
    )


def firebase_ai_logic_http_status(exc: FirebaseAILogicError) -> int:
    message = str(exc).lower()
    if "timed out" in message:
        return 504
    if any(marker in message for marker in (
        "not configured", "not authorized", "only with provisioned throughput",
        "not documented for location",
    )):
        return 503
    return 502


def _extract_text(response_data: dict[str, Any]) -> str:
    candidates = response_data.get("candidates") or []
    if not candidates:
        raise FirebaseAILogicError("Firebase AI Logic returned no model candidates.")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    text = "".join(value for value in text_parts if isinstance(value, str)).strip()
    if not text:
        feedback = response_data.get("promptFeedback") or {}
        reason = feedback.get("blockReason")
        suffix = f" ({reason})" if reason else ""
        raise FirebaseAILogicError(f"Firebase AI Logic did not return text content{suffix}.")
    return text


def _parse_json_text(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise FirebaseAILogicError("Firebase AI Logic returned a response that was not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise FirebaseAILogicError("Firebase AI Logic returned JSON in an unexpected format.")
    return parsed


async def _default_access_token_provider() -> str:
    """Get a short-lived OAuth token from ADC (Cloud Run service identity)."""
    def refresh_token() -> str:
        try:
            import google.auth
            from google.auth.transport.requests import Request
        except ImportError as exc:  # pragma: no cover - covered by deployment check
            raise FirebaseAILogicError(
                "The google-auth package is required for server-side Firebase AI Logic requests."
            ) from exc
        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            if not credentials.valid or not credentials.token:
                credentials.refresh(Request())
            if not credentials.token:
                raise FirebaseAILogicError("Google Application Default Credentials returned no access token.")
            return str(credentials.token)
        except FirebaseAILogicError:
            raise
        except Exception as exc:
            raise FirebaseAILogicError(
                "The backend could not obtain Google Application Default Credentials for Firebase AI Logic."
            ) from exc

    return await asyncio.to_thread(refresh_token)


async def generate_from_template(
    *,
    template_id: str,
    prompt: str,
    app_check_token: str,
    settings: Settings | None = None,
    http_client: httpx.AsyncClient | None = None,
    access_token_provider: Callable[[], Awaitable[str]] | None = None,
) -> dict[str, Any]:
    """Generate JSON through Firebase AI Logic's server prompt-template API.

    End-user Firebase Auth and App Check are verified by FastAPI before this
    function is called. The REST API itself requires OAuth cloud-platform
    authorization, supplied by the backend's ADC service identity.
    """
    cfg = settings or get_settings()
    if not cfg.firebase_project_id or not cfg.firebase_api_key:
        raise FirebaseAILogicError("Firebase project configuration is incomplete on the backend.")
    if not template_id:
        raise FirebaseAILogicError("The Firebase AI Logic prompt template is not configured.")
    if cfg.require_app_check and not app_check_token:
        raise FirebaseAILogicError("A verified Firebase App Check token is required.")
    validate_model_location(
        cfg.firebase_ai_logic_model,
        cfg.firebase_ai_logic_location,
        cfg.firebase_ai_logic_provisioned_throughput_enabled,
    )

    access_token = await (access_token_provider or _default_access_token_provider)()
    template_name = (
        f"projects/{cfg.firebase_project_id}/locations/"
        f"{cfg.firebase_ai_logic_location}/templates/{template_id}"
    )
    url = f"https://firebasevertexai.googleapis.com/v1beta/{template_name}:templateGenerateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": cfg.firebase_api_key,
        "Authorization": f"Bearer {access_token}",
    }
    if app_check_token:
        headers["X-Firebase-AppCheck"] = app_check_token
    if cfg.firebase_app_id:
        headers["X-Firebase-AppId"] = cfg.firebase_app_id

    timeout = httpx.Timeout(cfg.firebase_ai_logic_timeout_seconds, connect=20.0)
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=timeout)
    try:
        response = await client.post(url, headers=headers, json={"inputs": {"prompt": prompt}})
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise FirebaseAILogicError("Firebase AI Logic did not respond before the request timed out.") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 401:
            message = "Firebase AI Logic rejected the backend OAuth credentials. Check the Cloud Run service identity."
        elif status == 403:
            message = "Firebase AI Logic denied this request. Check the service identity permissions, App Check and project configuration."
        elif status == 404:
            message = "The Firebase AI Logic template or model/location combination was not found."
        elif status == 429:
            message = "Firebase AI Logic is temporarily rate limited. Please retry shortly."
        else:
            message = f"Firebase AI Logic returned an upstream error (HTTP {status})."
        raise FirebaseAILogicError(message) from exc
    except httpx.RequestError as exc:
        raise FirebaseAILogicError("The backend could not connect to Firebase AI Logic.") from exc
    finally:
        if owns_client:
            await client.aclose()

    try:
        data = response.json()
    except ValueError as exc:
        raise FirebaseAILogicError("Firebase AI Logic returned an unreadable response.") from exc
    if not isinstance(data, dict):
        raise FirebaseAILogicError("Firebase AI Logic returned an unexpected response.")
    return _parse_json_text(_extract_text(data))
