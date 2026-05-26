# Phase 8 Report — Real Provider Enablement

## 1. Goal

Enable real local providers by default while keeping graceful fallback for unstable runtime conditions.

## 2. Implemented

- Enabled Ollama primary LLM path with `gemma3:4b` and configurable mock fallback.
- Added compact structured-output prompt contract for local LLM reliability.
- Added `/runtime/providers` endpoint for configured provider/fallback status.
- Implemented `local_whisper` STT provider using `faster-whisper`.
- Implemented STT fallback chain: `local_whisper` -> `file` -> `mock` when allowed.
- Implemented `local_espeak` and `local_piper` TTS providers.
- Implemented TTS fallback chain with `cached_file` fallback when allowed.
- Updated Dockerfiles, Compose env defaults, model cache volumes, docs, and tests.

## 3. Changed Files

- `.env.example`
- `.gitignore`
- `README.md`
- `docker-compose.yml`
- `docs/03_api_spec.md`
- `docs/05_phase_plan.md`
- `docs/06_provider_strategy.md`
- `docs/07_test_strategy.md`
- `services/ai-orchestrator/app/agents/answer_analyzer.py`
- `services/ai-orchestrator/app/core/settings.py`
- `services/ai-orchestrator/app/main.py`
- `services/ai-orchestrator/app/models.py`
- `services/ai-orchestrator/app/providers/llm_router.py`
- `services/ai-orchestrator/app/services/orchestrator.py`
- `services/ai-orchestrator/tests/test_api_flow.py`
- `services/ai-orchestrator/tests/test_provider_router.py`
- `services/stt-service/Dockerfile`
- `services/stt-service/app/main.py`
- `services/stt-service/pyproject.toml`
- `services/stt-service/tests/test_stt_service.py`
- `services/tts-service/Dockerfile`
- `services/tts-service/app/main.py`
- `services/tts-service/tests/test_tts_service.py`

## 4. Test Result

- `../../.venv/bin/pytest` in `services/ai-orchestrator`: 16 passed
- `../../.venv/bin/pytest` in `services/stt-service`: 5 passed
- `../../.venv/bin/pytest` in `services/tts-service`: 4 passed
- `../../.venv/bin/pytest` in `services/discord-bot`: 4 passed
- `../../.venv/bin/pytest` in `services/dashboard`: 2 passed
- `docker compose config --quiet`: passed
- `git diff --check`: passed

## 5. Validation

- Host Ollama `/api/tags` returned `gemma3:4b` and `deepseek-r1:8b`.
- Container Orchestrator could access `http://host.docker.internal:11434/api/tags`.
- `GET /runtime/providers` showed `ollama`, `local_whisper`, and `local_espeak`.
- TTS runtime smoke returned `provider=local_espeak`, `fallback_used=false`.
- STT runtime smoke returned `provider=local_whisper`, `fallback_used=false`.
- Orchestrator answer flow recorded `agent_logs.provider=ollama`, `fallback_used=false`.
- Discord bot reconnected after rebuild.

## 6. Known Issues

- `local_whisper` downloads model files into ignored `models/whisper` on first real transcription.
- Piper is implemented as an adapter but needs an external Piper binary/model before it can be the primary TTS path.
- Real Discord voice receive is still file-based fallback oriented.

## 7. Next Actions

- Add an admin command or dashboard panel that surfaces runtime provider/fallback status.
- Add Piper model provisioning docs once a Korean Piper model is selected.
- Add real microphone/audio capture once Discord voice receive is stabilized.

## 8. Commit Message

phase 8: enable real providers with graceful fallback
- Added:
- Changed:
- Tested:
- Docs:
- Report:
