# Phase 10 — Discord Voice Receive

## Goal

Capture real Discord microphone audio for survey answers instead of relying on a
manually supplied audio file path. Root issue: spoken answers were never recognized
because the bot had no voice-receive path — only `!survey voice-file <path>` existed.

## Implemented

- Replaced the unused `davey` dependency (DAVE E2E encryption, not voice receive)
  with `discord-ext-voice-recv`.
- Added `app/voice_recorder.py` `VoiceRecorder`: buffers decoded 48kHz/16-bit/stereo
  PCM and writes a wav, decoupled from discord.py for unit testing.
- Added `!survey voice-listen`: connects with `voice_recv.VoiceRecvClient`, records the
  requesting user via `BasicSink`, auto-stops on silence or max window, writes wav to
  `AUDIO_DIR`, and submits through the existing `submit_audio_file` → STT flow.
- Added `_capture_until_silence` poll loop with `VOICE_SILENCE_TIMEOUT_SEC` /
  `VOICE_MAX_RECORD_SEC`.
- Added `libopus0` to the discord-bot image for opus decode.
- Env, compose, phase plan, README updated.

## Changed files

- `services/discord-bot/app/voice_recorder.py` (new)
- `services/discord-bot/app/main.py`
- `services/discord-bot/app/settings.py`
- `services/discord-bot/pyproject.toml`, `services/discord-bot/Dockerfile`
- `services/discord-bot/tests/test_voice_recorder.py` (new)
- `.env.example`, `docker-compose.yml`
- `docs/05_phase_plan.md`, `README.md`

## Test result

- discord-bot pytest: 8 passed (added 4: wav round-trip, reset, silence auto-stop,
  no-audio → None).
- Ran with the temp Python 3.14 venv + `pytest-asyncio` because the synced `.venv`
  targets macOS aarch64.

## Validation

- Unit-level PCM buffering, wav encoding, and silence/no-audio capture logic verified.
- NOT run this session: real Discord voice receive (needs live bot token + voice
  channel) and Docker rebuild.

## Known issues / Next actions

- The discord.py-specific glue (`VoiceRecvClient`, `BasicSink`, opus decode) is not
  unit covered — only the decoupled recorder/capture logic is. Manual smoke required:
  `!survey voice-start` → join voice → `!survey voice-listen` → speak → confirm STT
  transcript and orchestrator answer.
- Whisper transcribes the 48kHz stereo wav directly; if accuracy is poor, consider
  downmix to 16kHz mono before submit.
- Pairs with Phase 9: Korean TTS playback still needs a piper-compatible model.

## Commit message

phase 10: capture discord voice answers via voice-recv
