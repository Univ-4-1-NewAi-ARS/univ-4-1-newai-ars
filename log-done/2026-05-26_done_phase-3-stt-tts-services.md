# Done — Phase 3 STT/TTS Services

## Summary

Built STT and TTS FastAPI services with mock/file and cached-file behavior.

## Artifacts

- `services/stt-service`
- `services/tts-service`
- Orchestrator speech service adapters
- Service endpoint tests

## Tests

- Orchestrator pytest: PASS, 10 tests
- STT service pytest: PASS, 2 tests
- TTS service pytest: PASS, 2 tests
- `docker compose config`: PASS

## Result

Phase 3 implementation is locally validated. Runtime container smoke is still pending on Docker Desktop availability.

## Next

Proceed to Phase 4 Discord Bot text mode.
