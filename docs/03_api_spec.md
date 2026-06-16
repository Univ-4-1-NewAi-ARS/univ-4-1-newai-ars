# API Spec

이 문서는 Phase 0의 설계 기준이다. Phase 1 이후 구현과 함께 요청/응답 예시를 실제 schema에 맞춰 갱신한다.
Phase 1 기준으로 AI Orchestrator text/mock flow가 구현되어 있다.

## Orchestrator API

### `GET /health`

서비스 상태를 확인한다.

Response:

```json
{
  "status": "ok",
  "service": "ai-orchestrator",
  "repository": "postgres"
}
```

### `POST /sessions`

설문 세션을 시작한다.

Request:

```json
{
  "survey_id": "campus_opinion_survey",
  "participant_ref": "discord:masked-user-id",
  "channel": "discord_text"
}
```

Response:

```json
{
  "session_id": "uuid",
  "survey_id": "campus_opinion_survey",
  "status": "in_progress",
  "current_question": {
    "question_id": "q1",
    "text": "현재 캠퍼스 시설에 얼마나 만족하시나요?",
    "answer_type": "single_choice",
    "options": [
      {"id": "1", "label": "매우 만족"},
      {"id": "2", "label": "만족"},
      {"id": "3", "label": "보통"},
      {"id": "4", "label": "불만족"}
    ]
  },
  "tts": {
    "audio_path": "/data/tts/campus_opinion_survey-q1-ko_default.wav",
    "duration_sec": 3.1,
    "provider": "mock",
    "cached": true
  }
}
```

### `POST /sessions/{session_id}/answers`

응답을 제출하고 다음 질문 또는 완료 상태를 받는다.

Request:

```json
{
  "question_id": "q1",
  "transcript": "만족합니다",
  "audio_path": null,
  "source": "discord_text"
}
```

Response:

```json
{
  "session_id": "uuid",
  "status": "in_progress",
  "agent_result": {
    "question_id": "q1",
    "raw_transcript": "만족합니다",
    "cleaned_text": "만족합니다",
    "answer_type": "single_choice",
    "selected_option": "2",
    "confidence": 0.86,
    "sentiment": "positive",
    "keywords": ["만족"],
    "needs_retry": false,
    "review_required": false,
    "reason": "응답이 선택지 '만족'과 직접 매칭됨"
  },
  "next_question": {
    "question_id": "q2",
    "text": "가장 개선이 필요한 영역은 무엇인가요?"
  },
  "tts": {
    "audio_path": "/data/tts/campus_opinion_survey-q2-ko_default.wav",
    "duration_sec": 2.9,
    "provider": "mock",
    "cached": true
  }
}
```

### `GET /sessions/{session_id}/summary`

세션 요약과 저장된 응답을 반환한다.

Response:

```json
{
  "session_id": "uuid",
  "survey_id": "campus_opinion_survey",
  "status": "completed",
  "current_question_id": null,
  "response_count": 3,
  "responses": []
}
```

## Phase 1 구현 메모

- `POST /sessions`는 YAML survey definition을 로드하고 PostgreSQL 또는 memory repository에 session을 생성한다.
- `POST /sessions/{session_id}/answers`는 transcript 또는 `audio_path`를 받는다.
- transcript가 없고 `audio_path`가 있으면 mock STT provider가 transcript를 생성한다.
- mock LLM provider는 single-choice option matching과 free-text acceptance를 수행한다.
- agent result는 Pydantic 모델로 검증되고 `survey_responses.agent_result` JSONB에 저장된다.

### `GET /surveys/{survey_id}/stats`

설문 전체 통계를 반환한다.

Response:

```json
{
  "survey_id": "campus_opinion_survey",
  "session_count": 3,
  "response_count": 4,
  "option_counts": {
    "q1": {"2": 2}
  },
  "sentiment_counts": {
    "positive": 4
  },
  "generated_at": "2026-05-26T16:38:09.762583Z"
}
```

### `GET /surveys/{survey_id}/insights`

저장된 응답을 종합해 의견 인사이트를 반환한다. dashboard "의견 종합" 페이지가 소비한다.
선택지 응답은 option id를 사람이 읽는 label로 매핑하고, 자유응답은 키워드 빈도와 의견 목록으로 종합한다.
`SAVE_TRANSCRIPT=false`로 redacted된 자유응답 텍스트는 의견 목록에서 제외한다.

Response:

```json
{
  "survey_id": "campus_opinion_survey",
  "response_count": 45,
  "sentiment_counts": {"positive": 28, "neutral": 10, "negative": 7},
  "keyword_counts": {"만족": 18, "시설": 16, "도서관": 5},
  "questions": [
    {
      "question_id": "q1",
      "text": "현재 캠퍼스 시설에 얼마나 만족하시나요?",
      "answer_type": "single_choice",
      "response_count": 24,
      "sentiment_counts": {"positive": 22},
      "option_counts": {"만족": 19, "보통": 2},
      "keyword_counts": {},
      "opinions": []
    },
    {
      "question_id": "q2",
      "text": "가장 개선이 필요한 영역은 무엇인가요?",
      "answer_type": "free_text",
      "response_count": 11,
      "sentiment_counts": {"negative": 7},
      "option_counts": {},
      "keyword_counts": {"도서관": 5, "부족": 4},
      "opinions": [
        {"text": "도서관 좌석이 더 필요합니다", "sentiment": "negative", "keywords": ["library", "seats"], "confidence": 0.86}
      ]
    }
  ],
  "generated_at": "2026-06-16T00:00:00Z"
}
```

### `POST /surveys/{survey_id}/reports`

Markdown report를 생성하고 report path를 반환한다.

Response:

```json
{
  "survey_id": "campus_opinion_survey",
  "report_path": "/reports/20260526_163809_campus_opinion_survey_summary.md",
  "generated_at": "2026-05-26T16:38:09.857045Z"
}
```

### `GET /runtime/providers`

Phase 8에서 추가된 runtime provider configuration endpoint다. 실제 provider 우선 설정과 fallback 허용 상태를 빠르게 확인한다.

Response:

```json
{
  "llm": {
    "provider": "ollama",
    "base_url": "http://host.docker.internal:11434",
    "model": "gemma3:4b",
    "api_fallback_enabled": true,
    "mock_fallback_enabled": true,
    "timeout_sec": 45.0,
    "status": "configured"
  },
  "stt": {
    "provider": "local_whisper",
    "base_url": "http://stt-service:8100",
    "model": "small",
    "language": "ko",
    "mock_fallback_enabled": true,
    "status": "configured"
  },
  "tts": {
    "provider": "local_espeak",
    "base_url": "http://tts-service:8200",
    "voice": "ko_default",
    "language": "ko",
    "fallback_provider": "cached_file",
    "cached_fallback_enabled": true,
    "cache_enabled": true,
    "status": "configured"
  }
}
```

### `POST /retention/audio/cleanup`

Phase 7에서 추가된 raw audio retention cleanup endpoint다. `dry_run=true`가 기본이며, 실제 파일 삭제는 `dry_run=false`일 때만 수행한다. 삭제 대상은 `AUDIO_DIR` 하위 경로로 제한한다.

Query:

```text
dry_run=true | false
```

Response:

```json
{
  "expired_records": 1,
  "deleted_files": 1,
  "missing_files": 0,
  "skipped_files": 0,
  "dry_run": false,
  "record_ids": ["uuid"]
}
```

Privacy notes:

- `participant_ref`는 Orchestrator에서 hash/masked reference로 정규화한 뒤 저장한다.
- `SAVE_TRANSCRIPT=false`이면 `raw_transcript`, `cleaned_text`, `agent_result`의 transcript fields를 redacted marker로 저장/응답한다.
- `SAVE_RAW_AUDIO=true`일 때만 input audio path를 `audio_records`에 저장하고, `RAW_AUDIO_RETENTION_DAYS`로 만료 시각을 계산한다.

### `GET /audit/events`

audit_events(중요 로그)를 최신순으로 반환한다. dashboard의 "중요 로그" 페이지가 소비한다.

Query:

```text
limit=1..200 (기본 50)
```

Response:

```json
{
  "count": 2,
  "events": [
    {
      "id": "uuid",
      "event_type": "answer_processed",
      "severity": "info",
      "session_id": "uuid",
      "actor_ref": "hash:...",
      "details": {"question_id": "q1", "source": "discord_voice", "fallback_used": false},
      "created_at": "2026-06-16T00:00:00Z"
    }
  ]
}
```

## Dashboard API

Phase 6에서 FastAPI dashboard service가 구현되었고, 2026-06-16에 멀티페이지로 재구성되었다.
공유 상단 네비게이션 + 인라인 CSS로 다음 페이지를 제공한다.

- `GET /health` — JSON 헬스(머신용, 변경 없음)
- `GET /` — 요약 페이지 (기본 survey stats: sessions/responses, sentiment 막대, option 분포)
- `GET /surveys/{survey_id}` — 특정 survey 요약
- `GET /insights`, `GET /surveys/{survey_id}/insights` — 의견 종합 페이지 (핵심 키워드 클라우드 + 전체 감정 분포 + 질문별 선택지 분포/자유응답 의견 카드)
- `GET /services` — 서비스 헬스 페이지 (orchestrator/stt/tts `/health` ping + latency + provider 런타임 구성, 10초 자동 새로고침)
- `GET /logs` — 중요 로그 페이지 (orchestrator `/audit/events` 렌더, 심각도 badge, 10초 자동 새로고침)

요약/서비스/로그 데이터는 각각 Orchestrator의 `/surveys/{id}/stats`, `/health`+`/runtime/providers`,
`/audit/events`를 호출해 렌더링한다. 백엔드 호출 실패 시 500 대신 페이지 내 에러 배너로 graceful 처리한다.

## STT Service API

Phase 3에서 별도 FastAPI 서비스로 구현되었다.

### `GET /health`

```json
{
  "status": "ok",
  "service": "stt-service"
}
```

### `POST /transcribe`

Request:

```json
{
  "audio_path": "/data/audio/session-q1.wav",
  "language": "ko",
  "provider": "mock"
}
```

Response:

```json
{
  "text": "만족합니다",
  "language": "ko",
  "confidence": 0.9,
  "duration_sec": 2.4,
  "provider": "local_whisper",
  "fallback_used": false
}
```

구현 메모:

- `provider=mock`은 deterministic transcript를 반환한다.
- `provider=file`은 `/data/transcripts/{audio_stem}.txt`가 있으면 해당 파일 내용을 반환한다.
- `provider=local_whisper`은 `faster-whisper` 기반 local transcription을 수행한다.
- `local_whisper` 실패 시 file provider, 이후 `STT_USE_MOCK_FALLBACK=true`이면 mock provider로 fallback한다.
- Orchestrator는 `ServiceSTTProvider`를 통해 `/transcribe`를 호출할 수 있다.

## TTS Service API

Phase 3에서 별도 FastAPI 서비스로 구현되었다.

### `GET /health`

```json
{
  "status": "ok",
  "service": "tts-service"
}
```

구현 메모:

- `cached_file` provider는 `/data/tts/{survey_id}-{question_id}-{voice}.wav` 경로를 사용한다.
- 캐시 파일이 없으면 짧은 silent wav placeholder를 생성한다.
- `local_espeak` provider는 Docker 내부 `espeak-ng`로 provider-specific wav를 생성한다.
- `local_piper` provider는 `PIPER_BIN`과 `PIPER_MODEL_PATH`가 준비된 경우 사용한다.
- `gpt_sovits` provider는 GPT-SoVITS `api_v2` 서버(`POST /tts`)로 voice-cloning 합성을 요청하고 반환 wav를 저장한다. `GPT_SOVITS_REF_AUDIO_PATH`/`REF_TEXT`로 클론 보이스를 지정하며, 서버 미가동/미설정 시 fallback chain으로 graceful degrade한다.
- TTS 실패 시 `TTS_FALLBACK_PROVIDER`와 `TTS_USE_CACHED_FALLBACK` 설정에 따라 cached file fallback을 사용한다.
- Orchestrator는 `ServiceTTSProvider`를 통해 `/synthesize`를 호출할 수 있다.

### `POST /synthesize`

Request:

```json
{
  "text": "현재 캠퍼스 시설에 얼마나 만족하시나요?",
  "voice": "ko_default",
  "language": "ko",
  "provider": "cached_file"
}
```

Response:

```json
{
  "audio_path": "/data/tts/campus_opinion_survey-q1.wav",
  "duration_sec": 4.2,
  "provider": "local_espeak",
  "cached": false,
  "fallback_used": false
}
```

## Discord Bot to Orchestrator Flow

Phase 4 text mode uses command-prefix messages by default.

Commands:

- `!survey start [survey_id]`
- `!survey answer {text}`
- `!survey voice-start [survey_id]`
- `!survey voice-file {audio_path}`

Flow:

1. Bot receives `!survey start campus_opinion_survey`.
2. Bot calls `POST /sessions`.
3. Bot renders question text or plays returned TTS audio.
4. Bot captures text/audio answer.
5. Bot calls `POST /sessions/{session_id}/answers`.
6. Bot repeats until `status=completed`.
7. Bot calls summary endpoint and posts a short Discord message.

Implementation notes:

- If `DISCORD_MOCK_MODE=true` or `DISCORD_BOT_TOKEN=replace_me`, the bot starts in tokenless mock mode and does not connect to Discord.
- Discord user ids are hashed into `discord:{12-char-digest}` participant references before being sent to Orchestrator.
- Phase 5 voice MVP uses cached TTS audio paths and file-based audio answer submission as the stable fallback path.
