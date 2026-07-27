from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    TEMPORAL_HOST: str
    ANTHROPIC_API_KEY: str
    FASTAPI_PORT: int = 8000
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"
    X_MAC_SECRET: str = ""

    CLASSIFIER_MODEL: str = "claude-haiku-4-5-20251001"
    MAIN_AGENT_MODEL: str = "claude-sonnet-5"
    COMPACTOR_MODEL: str = "claude-haiku-4-5-20251001"

    FAST_TASK_QUEUE: str = "fast-tasks"
    LLM_TASK_QUEUE: str = "llm-tasks"
    FAST_TASK_MAX_CONCURRENT_ACTIVITIES: int = 20
    LLM_TASK_MAX_CONCURRENT_ACTIVITIES: int = 8

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    DEFAULT_WAKE_UP_SECONDS: int = 14400  # 4 hours, safe fallback
    ACTIVITY_HEARTBEAT_TIMEOUT_SECONDS: int = 30
    ACTIVITY_START_TO_CLOSE_TIMEOUT_SECONDS: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
