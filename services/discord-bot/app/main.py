from __future__ import annotations

import asyncio
import logging

from app.orchestrator_client import OrchestratorClient
from app.settings import Settings
from app.text_flow import TextSurveyManager
from app.voice_flow import VoiceSurveyManager
from app.voice_recorder import VoiceRecorder


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

        if content.startswith(f"{prefix} voice-listen"):
            await _record_voice_answer(message, voice_manager, settings, conversation_key)
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


async def _record_voice_answer(message, voice_manager, settings, conversation_key: str) -> None:
    active = voice_manager.sessions.get(conversation_key)
    if not active:
        await message.channel.send("진행 중인 음성 설문이 없습니다. 먼저 `!survey voice-start`를 입력해 주세요.")
        return
    if not getattr(message.author, "voice", None) or not message.author.voice:
        await message.channel.send("음성 채널에 먼저 들어가 주세요.")
        return
    try:
        from discord.ext import voice_recv
    except ImportError:
        await message.channel.send("voice receive 확장이 설치되지 않았습니다 (discord-ext-voice-recv).")
        return

    voice_client = message.guild.voice_client
    if not isinstance(voice_client, voice_recv.VoiceRecvClient):
        if voice_client:
            await voice_client.disconnect()
        voice_client = await message.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient)

    recorder = VoiceRecorder(audio_dir=settings.audio_dir)
    target_id = message.author.id

    def on_audio(user, data) -> None:
        if user is not None and getattr(user, "id", None) != target_id:
            return
        recorder.feed(getattr(data, "pcm", None))

    voice_client.listen(voice_recv.BasicSink(on_audio))
    await message.channel.send("🎙️ 듣고 있습니다. 답변을 말씀해 주세요...")

    audio_path = await _capture_until_silence(recorder, settings, active)
    voice_client.stop_listening()

    if audio_path is None:
        await message.channel.send(
            "음성을 인식하지 못했습니다. 다시 `!survey voice-listen`을 입력하거나 `!survey voice-file <경로>`를 사용해 주세요."
        )
        return

    result = await voice_manager.submit_audio_file(conversation_key=conversation_key, audio_path=audio_path)
    await message.channel.send(result["message"])
    if result["audio_path"]:
        await _try_play_voice_audio(message, result["audio_path"])


async def _capture_until_silence(recorder: VoiceRecorder, settings, active) -> str | None:
    """Poll the recorder until the speaker goes silent or the max window passes."""
    poll = 0.5
    elapsed = 0.0
    silent = 0.0
    last_bytes = 0
    while elapsed < settings.voice_max_record_sec:
        await asyncio.sleep(poll)
        elapsed += poll
        current = recorder.byte_count
        if current > last_bytes:
            last_bytes = current
            silent = 0.0
        elif recorder.has_audio:
            silent += poll
            if silent >= settings.voice_silence_timeout_sec:
                break

    if not recorder.has_audio:
        return None
    filename = f"{active.session_id}-{active.current_question_id}.wav"
    return recorder.write_wav(filename)


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
