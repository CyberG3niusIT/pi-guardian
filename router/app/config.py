from pathlib import Path

from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    ROUTER_HOST: str = "127.0.0.1"
    ROUTER_PORT: int = 8071
    LOG_LEVEL: str = "INFO"
    DEFAULT_MODEL: str = "qwen2.5-coder:1.5b"
    LARGE_MODEL: str = "qwen2.5-coder:3b"
    REQUEST_TIMEOUT: int = 120
    STREAM_DEFAULT: bool = False
    REQUIRE_API_KEY: bool = False
    ESCALATION_THRESHOLD: str = "medium"
    ADMIN_CLIENT_NAME: str = "Router_Admin_UI_Persistent"
    ADMIN_CLIENT_DESCRIPTION: str = "Dedizierter persistenter Admin-Client fuer die Router-UI"
    ADMIN_CLIENT_API_KEY: str = ""
    ADMIN_SESSION_COOKIE_NAME: str = "pi_guardian_admin_api_key"
    ADMIN_SESSION_COOKIE_MAX_AGE: int = 60 * 60 * 24 * 365
    ADMIN_ALLOWED_IP: str = "192.168.50.0/24"
    ADMIN_ALLOWED_ROUTES: str = (
        "/route,/health,/settings,/models,/models/select,/models/registry,/models/pull,/models/delete,"
        "/status/service,/clients,/history,/logs,/agents,/skills,/actions,/memory"
    )

    model_config = {"env_file": str(BASE_DIR / ".env")}


settings = Settings()
