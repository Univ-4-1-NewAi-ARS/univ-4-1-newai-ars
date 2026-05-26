# Phase 2 Report — Provider Router & Structured Output

## 1. Goal

Separate answer analysis from direct mock calls by adding provider routing, structured output validation, retry, and fallback behavior.

## 2. Implemented

- Added `AnswerAnalyzer` agent runner.
- Added `LLMRouter` with `mock`, `ollama`, `lmstudio`, and `openai` provider selection.
- Added Ollama and OpenAI-compatible provider skeletons.
- Added Pydantic `AgentResult` validation for all LLM outputs.
- Added parse/schema retry controlled by `LLM_PARSE_RETRY_COUNT`.
- Added graceful fallback to mock provider when configured providers are unavailable.
- Updated Orchestrator to store provider, retry count, fallback usage, and error messages in `agent_logs`.
- Added tests for default mock routing and unavailable Ollama fallback.

## 3. Changed Files

- `.env.example`
- `docs/01_architecture.md`
- `docs/05_phase_plan.md`
- `docs/06_provider_strategy.md`
- `services/ai-orchestrator/app/agents/*`
- `services/ai-orchestrator/app/providers/*`
- `services/ai-orchestrator/app/services/orchestrator.py`
- `services/ai-orchestrator/tests/*`

## 4. Test Result

- `../../.venv/bin/pytest` from `services/ai-orchestrator`: PASS, 8 tests

## 5. Validation

- `LLM_PROVIDER=mock` selects only the mock provider.
- `LLM_PROVIDER=ollama` with an unavailable local endpoint gracefully falls back to mock.
- Structured `AgentResult` remains validated before API responses and DB storage.

## 6. Known Issues

- Real Ollama, LM Studio, and OpenAI calls are skeleton-supported but not exercised because no local/API credentials were configured.
- Docker runtime smoke remains pending because Docker daemon was unavailable during Phase 1 validation.

## 7. Next Actions

- Phase 3: implement separate STT and TTS FastAPI services and connect Orchestrator to them through service providers.

## 8. Commit Message

```text
phase 2: provider router and structured output
- Added: LLM router, agent runner, provider skeletons, retry/fallback policy
- Changed: orchestrator records provider execution metadata in agent logs
- Tested: pytest
- Docs: architecture, provider strategy, phase plan
- Report: Phase 2 report and done log
```
