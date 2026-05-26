# Phase 7 Report — Hardening & Privacy

## 1. Goal

Implement the first privacy/hardening layer: sensitive text masking, participant reference normalization, audit event storage, raw audio retention cleanup, and fallback verification.

## 2. Implemented

- Added privacy utilities for masking provider errors, hashing raw participant references, computing retention deadlines, and checking safe file roots.
- Added `audit_events` schema and repository methods for operational/privacy event records.
- Added `audio_records` repository support and Orchestrator recording for file/audio answers when `SAVE_RAW_AUDIO=true`.
- Added `POST /retention/audio/cleanup` with `dry_run=true` default and `AUDIO_DIR` path guard.
- Added `SAVE_TRANSCRIPT=false` redaction for stored/returned transcript fields.
- Added tests for masking, participant hash normalization, transcript redaction, raw audio cleanup, and fallback logging.

## 3. Changed Files

- `.env.example`
- `docker-compose.yml`
- `docs/03_api_spec.md`
- `docs/04_data_model.md`
- `docs/05_phase_plan.md`
- `docs/07_test_strategy.md`
- `rules/guardrails.md`
- `infra/postgres/init/001_schema.sql`
- `services/ai-orchestrator/app/core/privacy.py`
- `services/ai-orchestrator/app/core/settings.py`
- `services/ai-orchestrator/app/db/schema.sql`
- `services/ai-orchestrator/app/main.py`
- `services/ai-orchestrator/app/models.py`
- `services/ai-orchestrator/app/agents/answer_analyzer.py`
- `services/ai-orchestrator/app/repositories/base.py`
- `services/ai-orchestrator/app/repositories/memory.py`
- `services/ai-orchestrator/app/repositories/postgres.py`
- `services/ai-orchestrator/app/services/orchestrator.py`
- `services/ai-orchestrator/tests/test_privacy_hardening.py`

## 4. Test Result

- `../../.venv/bin/pytest` in `services/ai-orchestrator`: 14 passed
- `../../.venv/bin/pytest` in `services/dashboard`: 2 passed
- `docker compose config --quiet`: passed
- `git diff --check`: passed

## 5. Validation

- Rebuilt/restarted Docker Orchestrator and Dashboard with `docker compose --profile dashboard up -d --build ai-orchestrator dashboard`.
- `GET http://localhost:8000/health`: passed
- `POST http://localhost:8000/retention/audio/cleanup?dry_run=true`: returned empty successful cleanup response
- `GET http://localhost:8501/health`: passed
- Orchestrator logs showed clean startup and successful retention endpoint request.

## 6. Known Issues

- Transcript time-based purge is not yet implemented; Phase 7 currently supports immediate transcript redaction through `SAVE_TRANSCRIPT=false`.
- Raw audio cleanup deletes only files visible to the Orchestrator container and only under `AUDIO_DIR`.

## 7. Next Actions

- Add scheduled retention jobs or admin automation for cleanup.
- Add transcript age-based redaction if long-running production retention needs it.
- Add structured app logging middleware if request-level audit traces become necessary.

## 8. Commit Message

phase 7: hardening privacy and retention
- Added:
- Changed:
- Tested:
- Docs:
- Report:
