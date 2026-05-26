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
    report_dir: Path = Field(default=Path("../../reports"))

    llm_provider: str = "mock"
    llm_base_url: str = "http://host.docker.internal:11434"
    llm_model: str = "qwen2.5:7b-instruct"
    llm_timeout_sec: float = 10.0
    llm_use_api_fallback: bool = True
    llm_parse_retry_count: int = 2
    openai_api_key: str = "replace_me"
    openai_model: str = "gpt-4.1-mini"
    stt_provider: str = "mock"
    stt_base_url: str = "http://stt-service:8100"
    tts_provider: str = "cached_file"
    tts_base_url: str = "http://tts-service:8200"
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
