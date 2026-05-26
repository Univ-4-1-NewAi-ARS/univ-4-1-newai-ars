# Phase 5 Report — Discord Voice MVP

## 1. Goal

Add the first Discord Voice MVP path: voice session start, cached TTS playback support, and stable file-based audio answer fallback.

## 2. Implemented

- Added Discord voice dependencies for playback support: `PyNaCl` and container `ffmpeg`.
- Added `VoiceSurveyManager` for voice session tracking.
- Added Orchestrator client audio-answer submission.
- Added Discord text commands:
  - `!survey voice-start [survey_id]`
  - `!survey voice-file {audio_path}`
- Added best-effort Discord voice channel join and cached TTS playback through `FFmpegPCMAudio`.
- Added file-based voice answer fallback that submits `audio_path` to Orchestrator.
- Updated API/test docs with Phase 5 voice commands and manual test procedure.

## 3. Changed Files

- `docs/03_api_spec.md`
- `docs/05_phase_plan.md`
- `docs/07_test_strategy.md`
- `services/discord-bot/Dockerfile`
- `services/discord-bot/pyproject.toml`
- `services/discord-bot/app/main.py`
- `services/discord-bot/app/orchestrator_client.py`
- `services/discord-bot/app/voice_flow.py`
- `services/discord-bot/tests/test_voice_flow.py`

## 4. Test Result

- `../../.venv/bin/pytest` from `services/discord-bot`: PASS, 4 tests
- `../../.venv/bin/pytest` from `services/ai-orchestrator`: PASS, 10 tests
- `docker compose config --quiet`: PASS
- `STT_PROVIDER=file docker compose up -d --build ai-orchestrator discord-bot`: PASS
- Container voice-file smoke: PASS

## 5. Validation

- Voice session starts with `channel=discord_voice`.
- Orchestrator returns cached TTS path: `/data/tts/campus_opinion_survey-q1-ko_default.wav`.
- File-based audio answer `/data/audio/q1.wav` is submitted to Orchestrator.
- Orchestrator calls `stt-service /transcribe` and receives transcript `만족합니다`.
- Structured result maps the first answer to selected option `2`.
- Session advances from `q1` to `q2`.

## 6. Known Issues

- Real Discord voice channel playback was not manually verified because local `.env` has `DISCORD_MOCK_MODE=true`.
- Discord voice receive/recording is not implemented yet; `voice-file` is the stable fallback path for Phase 5.
- Generated cached TTS wav files are runtime data and remain ignored by git.

## 7. Next Actions

- Set `DISCORD_MOCK_MODE=false` locally for real Discord text/voice command validation.
- Add actual voice receive/recording or integrate a stable Discord voice receive library.
- Phase 6: stats endpoint, dashboard, and Markdown reports.

## 8. Commit Message

```text
phase 5: discord voice mvp with file fallback
- Added: voice survey manager, voice commands, audio answer client, ffmpeg/PyNaCl support
- Changed: Discord bot can start voice sessions and submit file-based audio answers
- Tested: discord-bot pytest, orchestrator pytest, compose config, container voice-file smoke
- Docs: API spec, phase plan, test strategy
- Report: Phase 5 report and done log
```
