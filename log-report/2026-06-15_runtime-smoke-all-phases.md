# Runtime Smoke — All Phases Validation

## Goal

Validate complete Docker runtime stack across Phase 0–10 artifacts. Prior sessions
ran pytest locally but left Docker smoke pending for Phases 1–5.

## Test environment

- Docker Desktop 28.0.4 (active)
- compose config: `docker compose --profile dashboard --profile devtools config` — OK
- Services: postgres, redis, ai-orchestrator, stt-service, tts-service
- All images built from current main branch

## Pytest results (local, temp Python 3.14 venv)

| service | result |
|---|---|
| ai-orchestrator | 16 passed |
| stt-service | 5 passed |
| tts-service | 5 passed |
| discord-bot | 11 passed |
| dashboard | 2 passed |
| **total** | **39 passed, 0 failed** |

## Docker image builds

- `docker compose build tts-service discord-bot` — both built
- Issue found/fixed: `discord-ext-voice-recv>=0.5.0` matched no release (all alpha).
  Fixed to `>=0.5.0a0`. Both images rebuilt successfully.

## HTTP endpoint smoke

| endpoint | result |
|---|---|
| `GET /health` (orchestrator) | `{"status":"ok","service":"ai-orchestrator","repository":"postgres"}` |
| `GET /health` (stt-service) | `{"status":"ok","provider":"local_whisper"}` |
| `GET /health` (tts-service) | `{"status":"ok","provider":"local_espeak"}` |
| `GET /runtime/providers` | LLM=ollama, STT=local_whisper, TTS=local_espeak |
| `POST /synthesize` (TTS) | `provider=local_espeak`, `fallback_used=false` |
| `POST /sessions` | 201 Created, session_id returned, q1 TTS path populated |
| `POST /sessions/{id}/answers` | LLM analysis, structured AgentResult, next question |
| `GET /surveys/{id}/stats` | `session_count=1`, `response_count=1`, sentiment dist |

## Phase coverage

- Phase 1 (orchestrator core): session create + answer submit + stats — confirmed
- Phase 2 (provider router): LLM router active, AgentResult structured output — confirmed
- Phase 3 (STT/TTS): `/synthesize` espeak real audio, health — confirmed
- Phase 4 (discord-bot image): image built — runtime needs Discord token (external)
- Phase 5 (voice MVP): image includes voice-listen path — Discord runtime external
- Phase 6 (stats dashboard): stats endpoint confirmed; dashboard not launched this session
- Phase 7 (hardening): privacy mask, audit log in code — unit tested
- Phase 8 (real providers): espeak real TTS, runtime/providers endpoint — confirmed
- Phase 9 (piper KR): local_espeak working KR TTS; piper pygoruut incompatibility documented
- Phase 10 (voice receive): discord-bot image built with voice-recv + downmix; token pending

## Known remaining manual steps

- Discord bot live token smoke: `!survey voice-start` + `!survey voice-listen` in a voice channel
- Dashboard UI: `scripts/services.sh on dashboard` + browser at port 8501
- Piper KR: find/train an espeak-phoneme Korean piper model

## Commit

chore: docker smoke validation all phases
