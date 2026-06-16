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
    audio_dir: Path = Field(default=Path("/data/audio"))

    llm_provider: str = "ollama"
    llm_base_url: str = "http://host.docker.internal:11434"
    llm_model: str = "gemma3:4b"
    llm_timeout_sec: float = 45.0
    llm_use_api_fallback: bool = True
    llm_use_mock_fallback: bool = True
    llm_parse_retry_count: int = 2
    openai_api_key: str = "replace_me"
    openai_model: str = "gpt-4.1-mini"
    stt_provider: str = "local_whisper"
    stt_base_url: str = "http://stt-service:8100"
    stt_model: str = "small"
    stt_use_mock_fallback: bool = True
    tts_provider: str = "local_espeak"
    tts_base_url: str = "http://tts-service:8200"
    tts_fallback_provider: str = "cached_file"
    tts_use_cached_fallback: bool = True
    tts_cache_enabled: bool = True
    tts_voice: str = "ko_default"
    tts_language: str = "ko"
    stt_language: str = "ko"

    save_raw_audio: bool = True
    save_transcript: bool = True
    raw_audio_retention_days: int = 7
    transcript_retention_days: int = 30
    participant_hash_salt: str = "replace_me"
    max_retry_per_question: int = 2
    # Free-text answers are open-ended: any captured opinion is valid, so a small
    # local LLM setting needs_retry=true should not re-ask the same question.
    # Keep retry behavior for single_choice (no option matched). Default off.
    free_text_retry_enabled: bool = False

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
