# Phase 3 Report — STT/TTS Services

## 1. Goal

Implement separate FastAPI STT and TTS services and allow the Orchestrator to communicate with them through provider adapters.

## 2. Implemented

- Added `stt-service` FastAPI app with `/health` and `/transcribe`.
- Added mock/file transcript strategy for STT.
- Added `tts-service` FastAPI app with `/health` and `/synthesize`.
- Added cached wav placeholder generation for TTS.
- Updated Docker Compose to build and run STT/TTS services with Uvicorn.
- Added Orchestrator `ServiceSTTProvider` and `ServiceTTSProvider` HTTP adapters.
- Added tests for service endpoints and Orchestrator service-client adapters.

## 3. Changed Files

- `docker-compose.yml`
- `docs/03_api_spec.md`
- `docs/05_phase_plan.md`
- `docs/06_provider_strategy.md`
- `services/ai-orchestrator/app/providers/speech.py`
- `services/stt-service/*`
- `services/tts-service/*`

## 4. Test Result

- `../../.venv/bin/pytest` from `services/ai-orchestrator`: PASS, 10 tests
- `../../.venv/bin/pytest` from `services/stt-service`: PASS, 2 tests
- `../../.venv/bin/pytest` from `services/tts-service`: PASS, 2 tests
- `docker compose config`: PASS

## 5. Validation

- STT service returns deterministic Korean transcript for mock audio input.
- TTS service creates cached wav placeholder files and returns output path.
- Orchestrator service adapters call `/transcribe` and `/synthesize` through HTTPX and validate responses.

## 6. Known Issues

- Docker runtime smoke remains pending because Docker daemon was unavailable earlier in the session.
- STT/TTS local model adapters are skeleton-level future work; Phase 3 focuses on mock/file/cached behavior.

## 7. Next Actions

- Phase 4: implement Discord bot text mode with tokenless mock mode and Orchestrator client flow.

## 8. Commit Message

```text
phase 3: stt and tts services
- Added: STT/TTS FastAPI services and orchestrator HTTP adapters
- Changed: compose builds/runs stt-service and tts-service
- Tested: orchestrator, stt-service, and tts-service pytest; docker compose config
- Docs: API spec, provider strategy, phase plan
- Report: Phase 3 report and done log
```
