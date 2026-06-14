from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    discord_bot_token: str = "replace_me"
    discord_mock_mode: bool = True
    discord_command_prefix: str = "!survey"
    orchestrator_base_url: str = "http://ai-orchestrator:8000"
    default_survey_id: str = "campus_opinion_survey"
    audio_dir: Path = Path("/data/audio")
    voice_silence_timeout_sec: float = 2.0
    voice_max_record_sec: float = 15.0

    @property
    def token_is_configured(self) -> bool:
        return bool(self.discord_bot_token and self.discord_bot_token != "replace_me")
