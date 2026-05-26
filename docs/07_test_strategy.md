# Test Strategy

## Unit Test

- survey YAML loader
- session state machine
- provider router selection
- structured output schema validation
- repository mapping
- privacy mask utility

## Integration Test

- Orchestrator + PostgreSQL repository
- Orchestrator + STT/TTS service mock
- session start to answer submission closed loop
- stats snapshot generation

## Service Health Check

각 FastAPI 서비스는 `/health` endpoint를 제공한다.

- `ai-orchestrator`: app, DB, Redis 연결 상태
- `stt-service`: provider configuration status
- `tts-service`: cache directory와 provider status

## Mock Provider Test

Mock provider는 외부 네트워크 없이 전체 흐름을 검증해야 한다.

- Mock STT: fixture transcript 반환
- Mock TTS: deterministic audio path 반환
- Mock LLM: schema-valid JSON 반환
- Mock Discord input: text transcript 또는 fixture audio path 제출

## Docker Compose Smoke Test

Phase 0:

```bash
docker compose config
```

Phase 1 이후:

```bash
docker compose up -d postgres redis ai-orchestrator
curl http://localhost:8000/health
pytest
```

## Discord Manual Test Procedure

1. `.env`에 Discord placeholder 대신 실제 token/channel id를 로컬로 설정한다.
2. `.env`가 git에 stage되지 않았는지 확인한다.
3. Bot을 실행한다.
4. Discord text channel에서 `!survey start campus_opinion_survey`를 입력한다.
5. 질문 출력, 응답 제출, summary 출력을 확인한다.
6. voice phase에서는 voice channel join, cached TTS 재생, 응답 수집을 별도 체크리스트로 기록한다.

Phase 4 local tests use HTTPX mock transport for the Orchestrator client and do not require a Discord token.
