from app.settings import Settings


def test_placeholder_token_is_not_configured() -> None:
    settings = Settings(discord_bot_token="replace_me", discord_mock_mode=False)

    assert settings.token_is_configured is False
