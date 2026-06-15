# Dashboard Multipage Reconstruction

## Goal

Rebuild the web dashboard at a higher level: split into separate pages for
(1) survey summary, (2) per-service health, (3) important log output.

## Backend addition (ai-orchestrator)

The "important logs" page needed a queryable data source. `audit_events` were
written but never readable over HTTP, so added a listing path:

- `models.py`: `StoredAuditEvent`, `AuditEventsResponse`
- `repositories/base.py`: abstract `list_audit_events(*, limit=50)`
- `repositories/memory.py`: most-recent-first slice
- `repositories/postgres.py`: `SELECT ... ORDER BY created_at DESC LIMIT $1` +
  `_audit_from_row` (JSONB details decode)
- `services/orchestrator.py`: `list_audit_events` (clamps limit to 1..200)
- `main.py`: `GET /audit/events?limit=N`

## Dashboard rewrite (services/dashboard/app/main.py)

- `Settings` gained `stt_base_url`, `tts_base_url`, `health_timeout_sec`.
- `DashboardClient` reworked to take `Settings`; methods: `get_stats`,
  `get_providers`, `get_audit_events`, `ping` (health + latency capture).
- Shared `_layout()` with a top nav (요약 / 서비스 헬스 / 중요 로그), inline CSS
  design system (cards, status badges, sentiment/option bars, tables).
- Pages:
  - `GET /` and `GET /surveys/{id}` — summary (sessions/responses metrics,
    sentiment share bars, per-question option bars).
  - `GET /services` — pings orchestrator/stt/tts `/health`, shows status badge +
    latency + provider runtime config; 10s auto-refresh.
  - `GET /logs` — renders `/audit/events` as a severity-badged table; 10s refresh.
  - `GET /health` — unchanged JSON (healthcheck/test stable).
- Backend failures render an in-page error banner instead of HTTP 500.

## Tests

- ai-orchestrator: **17 passed** (added `test_audit_events_endpoint_lists_recent_events`).
  Must force `LLM_PROVIDER=mock`; in Docker the default reaches real ollama and
  makes `test_text_flow` non-deterministic.
- dashboard: **5 passed** (added services/logs/nav tests; updated client signature).

## Runtime verification (live, post-rebuild)

- `GET /audit/events?limit=5` → real postgres events (answer_processed, session_started).
- `/` 200 (5.9KB), `/services` 200 (6.2KB), `/logs` 200 (22KB).
- `/services` shows AI Orchestrator 정상 12ms/postgres, STT 정상 8ms/local_whisper,
  TTS 정상 8ms/local_espeak + provider panel (ollama/local_whisper/local_espeak).
- `/logs` rendered 50 audit rows (23 answer_processed + 27 session_started).

## Commit

feat: multipage dashboard (summary/health/logs) + orchestrator audit events endpoint
