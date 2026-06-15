# Dashboard Opinion Insights ("의견 종합")

## Goal

Add a dashboard view that synthesizes/aggregates the collected opinions, not just
raw counts.

## Why a new backend endpoint

The existing `/surveys/{id}/stats` only returns `option_counts` and
`sentiment_counts` — it discards the actual opinion text and keywords. Synthesis
needs the qualitative content, so a dedicated endpoint was added that reads the
stored `agent_result`s.

## Backend (ai-orchestrator)

- `models.py`: `OpinionItem`, `QuestionInsight`, `SurveyInsightsResponse`.
- `services/orchestrator.py`: `get_survey_insights()` — reads
  `list_responses_for_survey`, groups by question, and aggregates:
  - global + per-question sentiment counts
  - global (top 20) + per-question keyword frequency
  - single_choice: option counts mapped from option id → human label
  - free_text: opinion list (cleaned_text + sentiment + keywords + confidence),
    newest-first, capped at 50, skipping `TRANSCRIPT_REDACTED_TEXT` entries
- `main.py`: `GET /surveys/{survey_id}/insights`.

No new repository method needed (reuses `list_responses_for_survey`).

## Dashboard

- `DashboardClient.get_insights(survey_id)`.
- New nav item "의견 종합" → `/insights` (and `/surveys/{id}/insights`).
- `_insights_body()` renders: 핵심 키워드 chip cloud, 전체 감정 분포 bars, and per
  question either an option-distribution table (single_choice) or sentiment-colored
  opinion quote cards with keyword chips (free_text). Extracted `_sentiment_table`
  and `_keyword_cloud` helpers; added quote/chip/cloud CSS.
- Backend failure → in-page error banner (no 500).

## Tests

- ai-orchestrator: **18 passed** (+`test_survey_insights_synthesizes_opinions`).
- dashboard: **6 passed** (+`test_insights_page_synthesizes_opinions`, nav updated).

## Live verification (real data, post-rebuild)

`GET /surveys/campus_opinion_survey/insights`: 45 responses; top keywords
만족(18)/시설(16)/캠퍼스(7)/도서관(5); sentiment positive 28 / neutral 10 / negative 7;
q1 options 만족 19 / 매우 만족 1 / 보통 2; q2,q3 free_text opinions with keywords.
`/insights` page: HTTP 200, 18.2KB, 44 keyword chips + 21 opinion cards.

## Observation (not a code bug)

A q2 opinion was "Please subscribe, like, and comment." — a known Whisper
hallucination on silent/noisy audio. Logged as STT VAD-tuning candidate in CLAUDE.md.

## Commit

feat: dashboard 의견 종합 page + orchestrator survey insights endpoint
