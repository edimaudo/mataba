import base64
import json

import pytest

from app.config import Settings
from app.credentials import CredentialConfigurationError, load_service_account_info


def _encoded_service_account():
    info = {
        "type": "service_account",
        "project_id": "mataba-test",
        "private_key_id": "test-key-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\\ntest\\n-----END PRIVATE KEY-----\\n",
        "client_email": "mataba-test@mataba-test.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    return base64.b64encode(json.dumps(info).encode()).decode()


def test_missing_service_account_configuration_uses_application_default_credentials():
    assert load_service_account_info(Settings(google_service_account_json_base64="")) is None


def test_valid_base64_service_account_json_is_parsed():
    result = load_service_account_info(Settings(google_service_account_json_base64=_encoded_service_account()))
    assert result is not None
    assert result["project_id"] == "mataba-test"
    assert result["type"] == "service_account"


@pytest.mark.parametrize("value", ["not-base64", base64.b64encode(b"not-json").decode()])
def test_malformed_service_account_configuration_is_rejected(value):
    with pytest.raises(CredentialConfigurationError):
        load_service_account_info(Settings(google_service_account_json_base64=value))


def test_non_service_account_json_is_rejected():
    encoded = base64.b64encode(json.dumps({"type": "authorized_user"}).encode()).decode()
    with pytest.raises(CredentialConfigurationError):
        load_service_account_info(Settings(google_service_account_json_base64=encoded))
