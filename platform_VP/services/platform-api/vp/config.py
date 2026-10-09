from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VP_", env_file=".env", extra="ignore")
    database_url: str = "sqlite+aiosqlite:///./platform.db"
    redis_url: str = ""
    qdrant_url: str = ""
    encryption_key: SecretStr = SecretStr("")
    bootstrap_email: str = ""
    bootstrap_password: SecretStr = SecretStr("")
    cookie_secure: bool = True
    session_hours: int = 12
    workers: int = 8
    lease_seconds: int = 120
    model_timeout_seconds: int = 90
    monthly_budget_micros: int = 100_000_000
    session_budget_micros: int = 500_000
    max_sessions: int = 20
    max_participants: int = 3
    max_debate_rounds: int = 2
    context_chars: int = 24000
    jev_enabled: bool = False
    jev_model: str = "jev-1.13.0"
    jev_api_key: SecretStr = SecretStr("")
    allow_private_endpoints: bool = False
    login_attempts: int = 8
    trusted_origins: str = "http://localhost:3080,http://127.0.0.1:3080"


settings = Settings()
