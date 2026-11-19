"""Load Google service-account credentials from environment configuration."""
from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from .config import Settings, get_settings


class CredentialConfigurationError(ValueError):
    """Raised when the configured service-account secret cannot be read safely."""


def load_service_account_info(settings: Settings | None = None) -> dict[str, Any] | None:
    """Return service-account JSON from base64 environment config, or None for ADC.

    Local development can use Application Default Credentials. Vercel functions do
    not provide Google metadata-server credentials, so production uses the same
    service account stored as a sensitive base64 environment variable.
    """
    cfg = settings or get_settings()
    encoded = cfg.google_service_account_json_base64.strip()
    if not encoded:
        return None
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        info = json.loads(decoded)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CredentialConfigurationError(
            "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64 must contain base64-encoded service-account JSON."
        ) from exc

    required = {"type", "project_id", "private_key", "client_email", "token_uri"}
    if not isinstance(info, dict) or not required.issubset(info) or info.get("type") != "service_account":
        raise CredentialConfigurationError(
            "The configured Google credential is not a valid service-account JSON object."
        )
    return info
