from __future__ import annotations

import asyncio
import logging

from app.orchestrator_client import OrchestratorClient
from app.settings import Settings
from app.text_flow import TextSurveyManager


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord-bot")


async def run_mock_mode(settings: Settings) -> None:
    logger.info("Discord bot running in mock mode. No token is required.")
    while True:
        await asyncio.sleep(3600)


async def run_discord_text_bot(settings: Settings) -> None:
    try:
        import discord
    except ImportError as exc:
        raise RuntimeError("discord.py is required for real Discord mode") from exc

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    manager = TextSurveyManager(
        client=OrchestratorClient(settings.orchestrator_base_url),
        default_survey_id=settings.default_survey_id,
    )

    @client.event
    async def on_ready():
        logger.info("Discord bot connected as %s", client.user)

    @client.event
    async def on_message(message):
        if message.author.bot:
            return
        content = message.content.strip()
        prefix = settings.discord_command_prefix
        conversation_key = f"{message.channel.id}:{message.author.id}"

        if content.startswith(f"{prefix} start"):
            parts = content.split(maxsplit=2)
            survey_id = parts[2] if len(parts) > 2 else settings.default_survey_id
            reply = await manager.start(
                conversation_key=conversation_key,
                discord_user_id=str(message.author.id),
                survey_id=survey_id,
            )
            await message.channel.send(reply)
            return

        if content.startswith(f"{prefix} answer"):
            transcript = content.removeprefix(f"{prefix} answer").strip()
            reply = await manager.answer(conversation_key=conversation_key, transcript=transcript)
            await message.channel.send(reply)

    await client.start(settings.discord_bot_token)


async def main() -> None:
    settings = Settings()
    if settings.discord_mock_mode or not settings.token_is_configured:
        await run_mock_mode(settings)
        return
    await run_discord_text_bot(settings)


if __name__ == "__main__":
    asyncio.run(main())
