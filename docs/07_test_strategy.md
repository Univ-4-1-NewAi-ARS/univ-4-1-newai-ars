# Test Strategy

## Unit Test

- survey YAML loader
- session state machine
- provider router selection
- structured output schema validation
- repository mapping
- privacy mask utility
- participant reference normalization
- transcript redaction when `SAVE_TRANSCRIPT=false`

## Integration Test

- Orchestrator + PostgreSQL repository
- Orchestrator + STT/TTS service mock
- session start to answer submission closed loop
- stats snapshot generation
- raw audio retention cleanup with `AUDIO_DIR` path guard
- fallback execution recorded in `agent_logs`

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
6. voice phase에서는 `!survey voice-start campus_opinion_survey`로 voice session을 시작한다.
7. 사용자가 음성 채널에 있으면 Bot이 cached TTS wav를 재생하는지 확인한다.
8. 안정적인 녹음 수신 전까지는 `!survey voice-file /data/audio/q1.wav`로 파일 기반 응답을 제출한다.

Phase 4 local tests use HTTPX mock transport for the Orchestrator client and do not require a Discord token.

## Dashboard and Report Test Procedure

1. `GET /surveys/{survey_id}/stats`로 세션 수, 응답 수, 선택지 count, sentiment count를 확인한다.
2. `POST /surveys/{survey_id}/reports`로 Markdown report 생성을 확인한다.
3. `REPORT_DIR`에 생성된 report 파일은 runtime artifact로 취급하며 git에 commit하지 않는다.
4. Dashboard profile 실행 후 `GET /surveys/{survey_id}` HTML 화면을 확인한다.

## Privacy and Retention Test Procedure

1. `mask_sensitive_text`가 API key, bearer token, email, phone-like text를 redacted marker로 바꾸는지 확인한다.
2. `POST /sessions`에 raw participant id를 넣어도 저장된 `participant_ref`가 `hash:` prefix로 정규화되는지 확인한다.
3. `SAVE_TRANSCRIPT=false`로 answer를 제출했을 때 summary와 stored response에 raw transcript가 남지 않는지 확인한다.
4. `RAW_AUDIO_RETENTION_DAYS=0`과 fixture audio file로 answer를 제출한 뒤 `POST /retention/audio/cleanup?dry_run=false`가 만료 파일과 DB record를 정리하는지 확인한다.
5. provider 실패 후 mock fallback이 사용되면 `agent_logs.fallback_used=true`로 남는지 확인한다.
