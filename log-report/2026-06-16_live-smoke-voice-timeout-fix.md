# Live Smoke — Discord Connect + Voice Pipeline Timeout Fix

## Goal

Start the pending manual verification (Discord live bot smoke) and rebuild +
re-run the full stack directly.

## Environment

- Docker 27.3.1, all images rebuilt from current `main` (clean `down` → `up -d --build`)
- Real `DISCORD_BOT_TOKEN` present in `.env` (live mode, not mock)
- Host Ollama `gemma3:4b` reachable at `host.docker.internal:11434`
- Providers: LLM=ollama, STT=local_whisper (small/ko/cpu), TTS=local_espeak

## Bug found and fixed

Live `!survey voice-start` loop crashed on the first audio answer submit with
`httpx.ReadTimeout`. Root cause: `OrchestratorClient._post/_get` hardcoded
`httpx.AsyncClient(timeout=10.0)`. An audio answer triggers STT (faster-whisper)
+ LLM (ollama gemma3:4b) on the orchestrator, which exceeds 10s on cold model
loads — so the bot aborted while the orchestrator was still processing.

Fix:
- `OrchestratorClient.__init__` now takes `timeout: float = 120.0` and uses it
  for the ad-hoc client in both `_post` and `_get`.
- `discord-bot` settings gained `orchestrator_timeout_sec: float = 120.0`
  (`ORCHESTRATOR_TIMEOUT_SEC`), wired into both client constructions in `main.py`.
- `.env.example` documents `ORCHESTRATOR_TIMEOUT_SEC=120` (>= orchestrator
  `LLM_TIMEOUT_SEC` + cold-load headroom).

Tests injecting a `client=` bypass the ad-hoc path, so the change is backward
compatible. `discord-bot` pytest: **11 passed** in the rebuilt image.

## Verification results

| check | result |
|---|---|
| clean rebuild | all 8 services `up`, postgres/redis healthy |
| `GET /health` (orch/stt/tts/dashboard) | all `ok` |
| Discord live login | connected as `univ_4-1_newai_ars#9517`, no timeout error |
| audio answer Q1 (cold) | whisper transcript `만족합니다` → LLM option `2`, positive, conf 0.95, ~3.3s |
| free_text answer Q2 | LLM sentiment `negative`, keywords `[주차 공간, 부족, 개선]` |
| persistence | summary `response_count=2`; stats aggregates 39 sessions / 37 responses |
| dashboard `/surveys/{id}` | renders live Sessions/Responses/Sentiment/Options tables |

## Live human-speech smoke — DONE (2026-06-16)

A human joined the voice channel and ran `!survey voice-start` twice. Both
surveys completed end-to-end (TTS → mic PCM capture → 16k downmix → STT → LLM →
next question → completion → disconnect). Captured transcripts:

- session 68f1f5c7 (3/3): q1 "만족합니다"→opt2/positive, q2 "도서관 좌석이 더
  필요합니다"→negative, q3 "전반적으로 좋습니다"→positive. Clean.
- session ce24214f (5 responses): q1/q3 fine; q2 re-asked 3× (max retry) then
  advanced.

The previously-fixed `ORCHESTRATOR_TIMEOUT_SEC=120` held — no ReadTimeout.

### Residual issues found in live smoke (tracked in CLAUDE.md)

1. **needs_retry over-trigger**: real gemma3:4b returned `needs_retry=True` for a
   valid free_text answer, forcing q2 to retry to the cap. Loosen free_text retry
   criteria in answer_analyzer (or ignore needs_retry for free_text).
2. **Whisper silence hallucination**: a retry/silence window captured
   "구독&좋아요&댓글 부탁드려요!" (Korean YouTube-outro hallucination). Apply STT
   `vad_filter` / `no_speech_threshold`.
3. **discord.opus.OpusError: corrupted stream**: voice_recv PacketRouter failed to
   decode some opus packets (third-party). Capture still completed; audio
   robustness/quality may be affected. Check lib version / decoder options.

## Commit

fix: configurable discord-bot orchestrator timeout (voice loop cold-start)
