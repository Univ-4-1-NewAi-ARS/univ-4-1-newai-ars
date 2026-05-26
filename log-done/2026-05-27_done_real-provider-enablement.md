# Done — Real Provider Enablement

## Summary

Implemented Phase 8 real provider enablement with graceful fallback.

## Artifacts

- Ollama primary LLM path using `gemma3:4b`
- `LLM_USE_MOCK_FALLBACK` control
- `local_whisper` STT provider with file/mock fallback
- `local_espeak` and `local_piper` TTS providers with cached fallback
- `/runtime/providers` endpoint
- Updated provider docs, test strategy, phase plan, API spec, README

## Tests

- AI Orchestrator pytest: 16 passed
- STT service pytest: 5 passed
- TTS service pytest: 4 passed
- Discord bot pytest: 4 passed
- Dashboard pytest: 2 passed
- Docker Compose config validation: passed
- `git diff --check`: passed
- Docker rebuild for STT/TTS/Orchestrator/Discord bot: passed
- Runtime provider smoke: passed

## Result

Default runtime now uses real local providers first and keeps explicit fallback paths for operational resilience.

## Next

Provision Piper Korean model assets and extend Discord voice receive beyond file-based fallback.
