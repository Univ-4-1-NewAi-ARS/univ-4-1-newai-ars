from __future__ import annotations

import asyncio
import logging

from app.orchestrator_client import OrchestratorClient
from app.settings import Settings
from app.text_flow import TextSurveyManager
from app.voice_flow import VoiceSurveyManager


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
    voice_manager = VoiceSurveyManager(
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

        if content.startswith(f"{prefix} voice-start"):
            parts = content.split(maxsplit=2)
            survey_id = parts[2] if len(parts) > 2 else settings.default_survey_id
            result = await voice_manager.start(
                conversation_key=conversation_key,
                discord_user_id=str(message.author.id),
                survey_id=survey_id,
            )
            await message.channel.send(result["message"])
            if result["audio_path"]:
                await _try_play_voice_audio(message, result["audio_path"])
            return

        if content.startswith(f"{prefix} voice-file"):
            audio_path = content.removeprefix(f"{prefix} voice-file").strip()
            result = await voice_manager.submit_audio_file(conversation_key=conversation_key, audio_path=audio_path)
            await message.channel.send(result["message"])
            if result["audio_path"]:
                await _try_play_voice_audio(message, result["audio_path"])
            return

        if content.startswith(f"{prefix} answer"):
            transcript = content.removeprefix(f"{prefix} answer").strip()
            reply = await manager.answer(conversation_key=conversation_key, transcript=transcript)
            await message.channel.send(reply)

    await client.start(settings.discord_bot_token)


async def _try_play_voice_audio(message, audio_path: str) -> None:
    if not getattr(message.author, "voice", None) or not message.author.voice:
        await message.channel.send("음성 채널에 먼저 들어가면 TTS 오디오를 재생할 수 있습니다.")
        return
    try:
        voice_client = message.guild.voice_client
        if not voice_client:
            voice_client = await message.author.voice.channel.connect()
        if voice_client.is_playing():
            voice_client.stop()
        import discord

        voice_client.play(discord.FFmpegPCMAudio(audio_path))
    except Exception as exc:
        await message.channel.send(f"음성 재생을 시작하지 못했습니다: {type(exc).__name__}")


async def main() -> None:
    settings = Settings()
    if settings.discord_mock_mode or not settings.token_is_configured:
        await run_mock_mode(settings)
        return
    await run_discord_text_bot(settings)


if __name__ == "__main__":
    asyncio.run(main())
