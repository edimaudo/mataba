from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Mataba API"
    environment: str = "development"
    firebase_project_id: str = ""
    firebase_api_key: str = ""
    firebase_app_id: str = ""
    google_service_account_json_base64: str = ""
    allowed_origins: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:4173,http://127.0.0.1:4173"
    require_app_check: bool = True
    check_revoked_firebase_tokens: bool = True
    max_document_characters: int = 150_000
    max_source_pages: int = 250
    max_api_request_bytes: int = 2_000_000
    analysis_requests_per_minute: int = 4
    followup_requests_per_minute: int = 15
    legal_qa_requests_per_minute: int = 10

    # Firebase AI Logic server-prompt-template REST configuration.
    firebase_ai_logic_location: str = "northamerica-northeast1"
    firebase_ai_logic_model: str = "gemini-3.8-flash"
    firebase_ai_logic_provisioned_throughput_enabled: bool = False
    firebase_ai_analysis_template_id: str = "mataba-contract-analysis-v1"
    firebase_ai_followup_template_id: str = "mataba-follow-up-v1"
    firebase_ai_legal_qa_template_id: str = "mataba-legal-qa-v1"
    firebase_ai_logic_timeout_seconds: float = 180.0

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
