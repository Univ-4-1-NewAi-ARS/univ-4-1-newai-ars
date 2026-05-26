from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    repository_provider: str = "postgres"

    postgres_db: str = "ars_survey"
    postgres_user: str = "ars_user"
    postgres_password: str = "change_me"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    redis_host: str = "redis"
    redis_port: int = 6379

    survey_dir: Path = Field(default=Path("../../surveys"))

    llm_provider: str = "mock"
    stt_provider: str = "mock"
    tts_provider: str = "cached_file"
    tts_voice: str = "ko_default"
    tts_language: str = "ko"
    stt_language: str = "ko"

    save_raw_audio: bool = True
    save_transcript: bool = True
    max_retry_per_question: int = 2

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
