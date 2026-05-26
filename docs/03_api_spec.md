# API Spec

이 문서는 Phase 0의 설계 기준이다. Phase 1 이후 구현과 함께 요청/응답 예시를 실제 schema에 맞춰 갱신한다.

## Orchestrator API

### `GET /health`

서비스 상태를 확인한다.

Response:

```json
{
  "status": "ok",
  "service": "ai-orchestrator"
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
  }
}
```

### `GET /sessions/{session_id}/summary`

세션 요약과 저장된 응답을 반환한다.

## STT Service API

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

## TTS Service API

### `GET /health`

```json
{
  "status": "ok",
  "service": "tts-service"
}
```

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

1. Bot receives `/survey start campus_opinion_survey`.
2. Bot calls `POST /sessions`.
3. Bot renders question text or plays returned TTS audio.
4. Bot captures text/audio answer.
5. Bot calls `POST /sessions/{session_id}/answers`.
6. Bot repeats until `status=completed`.
7. Bot calls summary endpoint and posts a short Discord message.
