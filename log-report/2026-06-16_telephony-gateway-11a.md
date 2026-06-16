# Phase 11a — Telephony Gateway (Twilio Programmable Voice, Option A)

## Goal

Let the existing ARS survey run over a **real phone call** via Twilio, bypassing
Discord (which is blocked by DAVE E2EE for audio receive). Lowest-difficulty path:
Twilio Programmable Voice + `<Gather input="speech">` so **Twilio does the STT** and
the gateway only submits transcripts to the channel-agnostic orchestrator. The whole
flow is verifiable locally with **no Twilio account and no phone**.

## What was built

New service `services/telephony-gateway/` (FastAPI, port 8300), mirroring
`services/dashboard/` structure:

- `app/main.py` — `Settings` (pydantic-settings, `env_file=.env`) + `create_app()`:
  - `POST /voice/incoming` (Twilio inbound webhook): hashes the caller `From` number
    to `phone:{12-char sha256}`, starts a session (`channel="phone"`), returns TwiML
    that speaks question 1 and a `<Gather input="speech" language=… action="/voice/answer">`.
    Per-call state kept in an in-memory dict keyed by Twilio `CallSid`.
  - `POST /voice/answer` (Gather callback): reads `SpeechResult`, submits it as the
    answer (`source="phone"`); next question → `<Say>`+`<Gather>`, completion →
    completion message + `<Hangup/>`. Empty speech re-prompts; unknown CallSid /
    orchestrator error → graceful `<Hangup/>`.
  - Question speaking supports BOTH `<Say language="ko-KR">{text}</Say>` (default,
    zero-config) AND optional `<Play>{PUBLIC_BASE_URL}/media/{wav}</Play>` when
    `TELEPHONY_USE_TTS_AUDIO=true` and `PUBLIC_BASE_URL` is set (plays the
    orchestrator's GPT-SoVITS/espeak audio on the phone).
  - `GET /media/{filename}` serves wav from `TTS_DIR` (`/data/tts`) with
    path-traversal protection (basename-only + realpath prefix check).
  - `GET /health` → `{"status":"ok","service":"telephony-gateway"}`.
- `app/orchestrator_client.py` — adapted from discord-bot's `OrchestratorClient`
  (httpx, `start_session`/`submit_answer`/`get_summary`, 422→`NoSpeechDetected`),
  defaulting channel/source to `"phone"`.
- `pyproject.toml` (fastapi/httpx/pydantic-settings/uvicorn + **python-multipart**
  for Twilio form posts; dev: pytest/pytest-asyncio), `Dockerfile` (python:3.11-slim,
  uvicorn :8300), `app/__init__.py`.
- `tests/test_telephony.py` — 8 tests with `httpx.MockTransport` faking the
  orchestrator + FastAPI `TestClient`.

### Cross-cutting changes (additive)

- `services/ai-orchestrator/app/models.py` — added `"phone"` to `SurveyChannel`
  literal (backward compatible).
- `docker-compose.yml` — new `telephony-gateway` block under a `telephony` profile
  (it is the phone-channel alternative to discord-bot, so it does not auto-start with
  `core`). Added `TTS_DIR`, `PUBLIC_BASE_URL`, `TELEPHONY_USE_TTS_AUDIO`,
  `TELEPHONY_PORT`, `ORCHESTRATOR_TIMEOUT_SEC`, `LANGUAGE` to the `x-app-env` anchor.
- `scripts/services.sh` — `telephony` group (= ai-orchestrator + telephony-gateway),
  `--profile telephony` enabled, service added to `ALL_SERVICES`/usage.
- `scripts/telephony_sim.sh` — local Twilio simulator (see below).
- `.env.example` — telephony vars with comments.
- Docs: `docs/08_telephony_gateway_design.md` status → "11a 구현 완료", `CLAUDE.md`
  (ports table + flow note + phase table + pytest + file map), `rules/guardrails.md`
  (Twilio cloud-audio + phone-hash + media note).

## How to verify locally (no phone, no Twilio)

`scripts/telephony_sim.sh [GATEWAY_URL] [FROM] [answers…]` POSTs the exact
form-encoded payloads Twilio sends (`CallSid`, `From`, `SpeechResult`) to
`/voice/incoming` then `/voice/answer` repeatedly, printing the TwiML at each step
until `<Hangup/>`. It drives the same code path a real call would.

Live end-to-end run (orchestrator with `LLM_PROVIDER=mock STT_PROVIDER=mock`):

```
scripts/services.sh on telephony        # or docker compose --profile telephony up -d
scripts/telephony_sim.sh
# incoming → Q1 <Say>+<Gather>
# answer   → Q2 <Say>+<Gather>
# answer   → Q3 <Say>+<Gather>
# answer   → "설문이 완료되었습니다" + <Hangup/>
# == survey completed (Hangup) after 4 turn(s) ==
```

Confirmed the session persisted with `channel=phone` and a hashed `actor_ref`
(`hash:…`, no raw number) in `GET /audit/events`, and `/surveys/.../stats`
response_count incremented.

## How a user enables it with Twilio

1. Expose the gateway over public HTTPS (e.g. `ngrok http 8300`).
2. In the Twilio console, set the phone number's **Voice → A Call Comes In** webhook
   to `https://<tunnel>/voice/incoming` (HTTP POST).
3. Call the number → hear the Korean question via `<Say>` → speak the answer →
   Twilio recognizes it (`SpeechResult`) → next question → … → completion + hangup.
4. (Optional) To play the orchestrator's own TTS audio instead of Twilio's voice,
   set `TELEPHONY_USE_TTS_AUDIO=true` and `PUBLIC_BASE_URL=https://<tunnel>`.

## Tests

- telephony-gateway: `8 passed` (incoming TwiML has Q1 + `<Gather>`; answer advances
  Q1→Q2 then completes with `<Hangup/>`; participant_ref is hashed and raw number not
  leaked; phone channel/source asserted on orchestrator calls; empty speech re-prompts;
  unknown CallSid hangs up; `<Play>` mode emits the media URL; media rejects traversal).
- ai-orchestrator: `22 passed` with `LLM_PROVIDER=mock` — adding `"phone"` to
  `SurveyChannel` broke nothing.
- Live sim: full 3-question phone survey completed end-to-end against the running
  orchestrator.

## Limitations / follow-ups

- **Privacy**: Option A runs STT in the Twilio cloud (audio leaves the host). For
  local whisper, implement Option B (Media Streams) / Option C (SIP) — designed in
  docs/08, not built here.
- Real Twilio number smoke (with a public tunnel) still pending — only the local
  simulation and a mock-orchestrator live run are verified.
- Per-call state is in-memory (single process); a multi-replica deploy would need a
  shared store. Fine for the PoC.
- Narrowband (8kHz) Korean STT accuracy on real calls is untested.
