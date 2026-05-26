from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    discord_bot_token: str = "replace_me"
    discord_mock_mode: bool = True
    discord_command_prefix: str = "!survey"
    orchestrator_base_url: str = "http://ai-orchestrator:8000"
    default_survey_id: str = "campus_opinion_survey"

    @property
    def token_is_configured(self) -> bool:
        return bool(self.discord_bot_token and self.discord_bot_token != "replace_me")
