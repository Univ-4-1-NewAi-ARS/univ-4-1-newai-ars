# Fix — q2 free_text repeated 3× (needs_retry over-trigger)

## Bug

In the live voice smoke, q2 ("가장 개선이 필요한 영역은?") was re-asked to the
retry cap (3 attempts) even though the transcript was correct
("도서관 좌석이 더 필요합니다"). Root cause: the real gemma3:4b returned
`needs_retry=true` on a valid free_text answer, and `submit_answer` honored it for
every answer type.

## Fix

Free_text answers are open-ended — any non-empty opinion is acceptable, so a small
local LLM flagging needs_retry must not loop the question.

- `core/settings.py`: `free_text_retry_enabled: bool = False` (`FREE_TEXT_RETRY_ENABLED`).
- `services/orchestrator.py`: new `_should_retry(question, agent_result)`; gates the
  retry branch. Free_text ignores needs_retry unless the setting is enabled;
  single_choice still retries on needs_retry (no option matched).
- `agents/answer_analyzer.py`: prompt clarified — needs_retry=true for single_choice
  only when no option matches; for free_text only when empty/unintelligible.
- `.env.example`: documents `FREE_TEXT_RETRY_ENABLED=false`.

## Tests

- ai-orchestrator **21 passed** (+`test_retry_policy.py`, 3 cases: free_text ignored,
  single_choice retried, toggle re-enables).
- Live (real ollama): session → q1 → q2 free_text advanced straight to q3
  (`needs_retry=False`, `next=q3`).

## Commit

fix: do not retry free_text answers on needs_retry (q2 3x loop)
