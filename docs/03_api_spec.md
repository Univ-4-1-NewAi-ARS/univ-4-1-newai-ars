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
  "provider": "mock"
}
```

구현 메모:

- `provider=mock`은 deterministic transcript를 반환한다.
- `provider=file`은 `/data/transcripts/{audio_stem}.txt`가 있으면 해당 파일 내용을 반환한다.
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
  "provider": "cached_file",
  "cached": true
}
```

## Discord Bot to Orchestrator Flow

Phase 4 text mode uses command-prefix messages by default.

Commands:

- `!survey start [survey_id]`
- `!survey answer {text}`

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
