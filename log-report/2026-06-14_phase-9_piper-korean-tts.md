# Phase 9 — Piper Korean TTS Enablement

## Goal

Activate the real `local_piper` TTS path with a Korean voice model while keeping
the existing `local_espeak` / `cached_file` fallback chain intact.

## Implemented

- Installed the `piper-tts` CLI in the `tts-service` Docker image via pyproject dependency.
- Added `scripts/provision_piper.sh` to download a Piper voice (`.onnx` + `.onnx.json`)
  into `models/piper/`, configurable through `PIPER_VOICE_REPO` / `PIPER_MODEL_FILE` /
  `PIPER_CONFIG_FILE`.
- Set the default Korean model path to `/models/piper/piper-kss-korean.onnx` in
  TTS settings, `.env.example`, and `docker-compose.yml`.
- Added a `local_piper` success-path unit test (provider-specific wav, `fallback_used=false`).
- Updated provider strategy, phase plan, env rules, and README.

## Changed files

- `scripts/provision_piper.sh` (new)
- `services/tts-service/pyproject.toml`
- `services/tts-service/Dockerfile` (piper installed via `pip install -e .`)
- `services/tts-service/app/main.py`
- `services/tts-service/tests/test_tts_service.py`
- `.env.example`, `docker-compose.yml`
- `docs/05_phase_plan.md`, `docs/06_provider_strategy.md`
- `rules/env_rules.md`, `README.md`

## Test result

- `tts-service` pytest: 5 passed (added `test_local_piper_synthesizes_wav`).
- Ran with a temporary Python 3.14 venv (`fastapi`, `pydantic`, `pydantic-settings`,
  `httpx`, `pytest`) because the synced `.venv` targets macOS aarch64 and is not
  runnable on this Windows host.

## Validation

- Unit-level synthesis success and fallback paths verified.
- `docker compose config` and Docker runtime smoke NOT run this session (Docker not
  exercised; model not downloaded).

## Known issues / Next actions

- Official `rhasspy/piper-voices` ships no Korean voice; default uses the community
  model `neurlang/piper-onnx-kss-korean`. Quality/licensing should be reviewed before
  any non-test use.
- Pending manual validation: run `scripts/provision_piper.sh`, set
  `TTS_PROVIDER=local_piper`, `scripts/services.sh rebuild tts-service`, then call
  `/synthesize` and confirm `provider=local_piper`, `fallback_used=false`.
- Other macOS-only `.venv` means full repo pytest + Docker smoke remain a host-side step.

## Commit message

phase 9: enable local piper korean tts with provisioning script
