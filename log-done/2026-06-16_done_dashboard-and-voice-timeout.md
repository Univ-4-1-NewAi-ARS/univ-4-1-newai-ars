# Done — Live Smoke, Voice Timeout Fix, Multipage Dashboard, Opinion Insights

Date: 2026-06-16
Branch: feature/voice-quality-stt-tts (baseline)

## Completed

- **Voice loop timeout fix**: `OrchestratorClient` 10s hardcoded timeout →
  configurable `ORCHESTRATOR_TIMEOUT_SEC=120`. Found via live smoke ReadTimeout.
- **Live human-speech smoke**: 2 voice surveys completed end-to-end; transcripts
  accurate. Residual issues logged (needs_retry over-trigger, Whisper silence
  hallucination, opus corrupted-stream).
- **Dashboard reconstruction**: multipage (요약 / 의견 종합 / 서비스 헬스 / 중요 로그)
  with shared nav + design system.
- **Orchestrator endpoints**: `GET /audit/events`, `GET /surveys/{id}/insights`.

## Tests

- ai-orchestrator 18 passed, dashboard 6 passed, discord-bot 11, stt 5, tts 5
  (total 45 passed). Orchestrator suite requires `LLM_PROVIDER=mock` for determinism.

## Reports

- log-report/2026-06-16_live-smoke-voice-timeout-fix.md
- log-report/2026-06-16_dashboard-multipage-reconstruction.md
- log-report/2026-06-16_dashboard-opinion-insights.md
