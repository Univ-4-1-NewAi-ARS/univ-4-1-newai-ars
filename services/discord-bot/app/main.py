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
        client=OrchestratorClient(settings.orchestrator_base_url, timeout=settings.orchestrator_timeout_sec),
        default_survey_id=settings.default_survey_id,
    )
    voice_manager = VoiceSurveyManager(
        client=OrchestratorClient(settings.orchestrator_base_url, timeout=settings.orchestrator_timeout_sec),
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

            if not getattr(message.author, "voice", None) or not message.author.voice:
                await message.channel.send("음성 채널에 먼저 들어가 주세요.")
                return

            result = await voice_manager.start(
                conversation_key=conversation_key,
                discord_user_id=str(message.author.id),
                survey_id=survey_id,
            )
            await message.channel.send(result["message"])
            # Launch the full TTS→listen→submit loop as a background task so
            # on_message returns immediately and other messages can be processed.
            asyncio.create_task(
                _voice_survey_loop(message, voice_manager, settings, conversation_key, result["audio_path"])
            )
            return

        if content.startswith(f"{prefix} voice-file"):
            # Manual fallback: supply a pre-recorded wav path.
            audio_path = content.removeprefix(f"{prefix} voice-file").strip()
            result = await voice_manager.submit_audio_file(conversation_key=conversation_key, audio_path=audio_path)
            await message.channel.send(result["message"])
            if result["audio_path"]:
                await _play_tts_only(message, result["audio_path"])
            return

        if content.startswith(f"{prefix} answer"):
            transcript = content.removeprefix(f"{prefix} answer").strip()
            reply = await manager.answer(conversation_key=conversation_key, transcript=transcript)
            await message.channel.send(reply)

    await client.start(settings.discord_bot_token)


async def _voice_survey_loop(
    message,
    voice_manager: VoiceSurveyManager,
    settings: Settings,
    conversation_key: str,
    initial_audio_path: str | None,
) -> None:
    """Full voice ARS loop: play TTS → listen → submit → repeat until done.

    Runs as a background task spawned by voice-start.
    """
    try:
        from discord.ext import voice_recv
        import discord
    except ImportError:
        await message.channel.send("voice receive 확장이 설치되지 않았습니다 (discord-ext-voice-recv).")
        return

    # Connect (or reconnect) with VoiceRecvClient so we can both play and capture.
    voice_client = message.guild.voice_client
    if not isinstance(voice_client, voice_recv.VoiceRecvClient):
        if voice_client:
            await voice_client.disconnect()
        try:
            voice_client = await message.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
        except Exception as exc:
            await message.channel.send(f"음성 채널 연결 실패: {type(exc).__name__}: {exc}")
            return

    # Play initial question TTS and wait for it to finish.
    if initial_audio_path:
        await _play_and_wait(voice_client, initial_audio_path, discord)

    # Survey answer loop — each iteration: listen for one answer.
    max_consecutive_empty = 3
    empty_count = 0

    while True:
        active = voice_manager.sessions.get(conversation_key)
        if not active:
            break

        recorder = VoiceRecorder(audio_dir=settings.audio_dir)
        target_id = message.author.id

        def on_audio(user, data) -> None:
            if user is not None and getattr(user, "id", None) != target_id:
                return
            recorder.feed(getattr(data, "pcm", None))

        voice_client.listen(voice_recv.BasicSink(on_audio))
        await message.channel.send("🎙️ 듣고 있습니다. 말씀해 주세요...")

        audio_path = await _capture_until_silence(recorder, settings, active)
        voice_client.stop_listening()

        if audio_path is None:
            empty_count += 1
            if empty_count >= max_consecutive_empty:
                await message.channel.send(
                    "음성을 인식하지 못해 설문을 종료합니다. "
                    "`!survey voice-file <경로>` 로 파일로 응답하거나 다시 `!survey voice-start`를 입력해 주세요."
                )
                voice_manager.sessions.pop(conversation_key, None)
                break
            await message.channel.send(
                f"음성을 인식하지 못했습니다. 다시 말씀해 주세요. ({empty_count}/{max_consecutive_empty})"
            )
            continue

        result = await voice_manager.submit_audio_file(
            conversation_key=conversation_key, audio_path=audio_path
        )

        # STT captured audio but heard no actual speech (e.g. noise/silence):
        # treat like an empty capture — re-ask instead of advancing.
        if result.get("no_speech"):
            empty_count += 1
            if empty_count >= max_consecutive_empty:
                await message.channel.send(
                    "음성을 인식하지 못해 설문을 종료합니다. "
                    "`!survey voice-file <경로>` 로 파일로 응답하거나 다시 `!survey voice-start`를 입력해 주세요."
                )
                voice_manager.sessions.pop(conversation_key, None)
                break
            await message.channel.send(f"{result['message']} ({empty_count}/{max_consecutive_empty})")
            continue

        empty_count = 0
        await message.channel.send(result["message"])

        if result["completed"]:
            break

        # Play next question TTS and wait before listening again.
        if result["audio_path"]:
            await _play_and_wait(voice_client, result["audio_path"], discord)

    # Disconnect politely after the survey ends.
    try:
        if voice_client.is_connected():
            await voice_client.disconnect()
    except Exception:
        pass


async def _play_and_wait(voice_client, audio_path: str, discord_module) -> None:
    """Play an audio file through voice_client and await its completion."""
    done = asyncio.Event()

    def after_cb(error: Exception | None) -> None:
        if error:
            logger.warning("TTS playback error: %s", error)
        done.set()

    if voice_client.is_playing():
        voice_client.stop()
    voice_client.play(discord_module.FFmpegPCMAudio(audio_path), after=after_cb)
    await done.wait()


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


async def _play_tts_only(message, audio_path: str) -> None:
    """Play TTS without waiting for completion (used by voice-file fallback)."""
    if not getattr(message.author, "voice", None) or not message.author.voice:
        return
    try:
        import discord
        voice_client = message.guild.voice_client
        if not voice_client:
            voice_client = await message.author.voice.channel.connect()
        if voice_client.is_playing():
            voice_client.stop()
        voice_client.play(discord.FFmpegPCMAudio(audio_path))
    except Exception as exc:
        await message.channel.send(f"음성 재생 실패: {type(exc).__name__}")


async def main() -> None:
    settings = Settings()
    if settings.discord_mock_mode or not settings.token_is_configured:
        await run_mock_mode(settings)
        return
    await run_discord_text_bot(settings)


if __name__ == "__main__":
    asyncio.run(main())
