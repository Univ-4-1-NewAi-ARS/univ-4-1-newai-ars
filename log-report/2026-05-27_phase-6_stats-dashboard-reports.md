# Phase 6 Report — Stats Dashboard and Reports

## 1. Goal

Add survey statistics, Markdown report export, and a lightweight dashboard for viewing survey results.

## 2. Implemented

- Added Orchestrator stats endpoint: `GET /surveys/{survey_id}/stats`.
- Added Orchestrator Markdown report endpoint: `POST /surveys/{survey_id}/reports`.
- Added repository methods for survey-wide response listing and session counts.
- Added Markdown report exporter writing to `REPORT_DIR`.
- Added FastAPI dashboard service with HTML rendering for survey stats.
- Updated Docker Compose dashboard profile to build/run the dashboard service.
- Added tests for stats/report export and dashboard rendering.

## 3. Changed Files

- `.env.example`
- `docker-compose.yml`
- `docs/03_api_spec.md`
- `docs/05_phase_plan.md`
- `docs/07_test_strategy.md`
- `services/ai-orchestrator/app/*`
- `services/ai-orchestrator/tests/test_stats_reports.py`
- `services/dashboard/*`

## 4. Test Result

- `../../.venv/bin/pytest` from `services/ai-orchestrator`: PASS, 11 tests
- `../../.venv/bin/pytest` from `services/dashboard`: PASS, 2 tests
- `docker compose config --quiet`: PASS
- `docker compose --profile dashboard up -d --build ai-orchestrator dashboard`: PASS
- `GET /surveys/campus_opinion_survey/stats`: PASS
- `POST /surveys/campus_opinion_survey/reports`: PASS
- `GET http://localhost:8501/health`: PASS
- `GET http://localhost:8501/surveys/campus_opinion_survey`: PASS

## 5. Validation

- Stats endpoint returns session count, response count, selected option counts, and sentiment counts.
- Markdown report is generated under `/reports` and mapped to local `reports/`.
- Dashboard renders HTML summary from Orchestrator stats.

## 6. Known Issues

- Dashboard is intentionally minimal FastAPI HTML, not a full Streamlit or rich UI.
- Report files are runtime artifacts and ignored by git.

## 7. Next Actions

- Phase 7: hardening, privacy masks, retention policy, audit/error handling.
- Improve dashboard UX once statistics stabilize.

## 8. Commit Message

```text
phase 6: stats dashboard and reports
- Added: survey stats endpoint, Markdown report exporter, FastAPI dashboard
- Changed: compose dashboard profile builds/runs the dashboard service
- Tested: orchestrator/dashboard pytest, compose config, runtime stats/report/dashboard smoke
- Docs: API spec, phase plan, test strategy
- Report: Phase 6 report and done log
```

