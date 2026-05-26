# Data Model

Phase 1에서 실제 PostgreSQL DDL을 `infra/postgres/init/001_schema.sql`와 Orchestrator 내부 schema bootstrap 파일에 구현했다. DB schema 변경 시 이 문서와 SQL 파일을 함께 갱신한다.

## `survey_sessions`

설문 세션 단위 상태를 저장한다.

- `id`: UUID primary key
- `survey_id`: survey definition id
- `participant_ref`: Discord user id 또는 external participant id의 masked reference
- `channel`: `discord_text`, `discord_voice`, `mock`
- `status`: `created`, `in_progress`, `completed`, `abandoned`, `failed`
- `current_question_id`: 현재 질문 id
- `retry_count`: 현재 질문 retry 횟수
- `started_at`: 시작 시각
- `completed_at`: 종료 시각
- `metadata`: JSONB 확장 필드

## `survey_responses`

질문별 응답과 agent 분석 결과를 저장한다.

- `id`: UUID primary key
- `session_id`: `survey_sessions.id`
- `question_id`: survey question id
- `raw_transcript`: 원문 transcript
- `cleaned_text`: 정제 transcript
- `answer_type`: 응답 유형
- `selected_option`: 선택지 id 또는 null
- `confidence`: agent confidence
- `sentiment`: sentiment label
- `keywords`: JSONB string array
- `needs_retry`: 재질문 필요 여부
- `review_required`: 수동 검토 필요 여부
- `reason`: agent 판단 이유
- `agent_result`: 전체 structured JSONB
- `created_at`: 저장 시각

## `audio_records`

음성 원본 또는 TTS 출력 파일 경로를 저장한다.

- `id`: UUID primary key
- `session_id`: `survey_sessions.id`
- `question_id`: 관련 질문 id
- `record_type`: `input_audio`, `tts_output`
- `file_path`: 컨테이너 기준 파일 경로
- `duration_sec`: 길이
- `provider`: 사용 provider
- `retention_until`: 보관 만료 시각
- `created_at`: 저장 시각

Phase 7부터 file/audio answer가 STT로 처리될 때 `SAVE_RAW_AUDIO=true`이면 `input_audio` record를 저장한다. Retention cleanup은 `retention_until`이 지난 record를 조회하고, `AUDIO_DIR` 하위 파일만 삭제 대상으로 취급한다.

## `stats_snapshots`

설문 통계 snapshot을 저장한다.

- `id`: UUID primary key
- `survey_id`: survey definition id
- `snapshot`: JSONB 통계 payload
- `generated_by`: `scheduled`, `manual`, `session_completed`
- `created_at`: 생성 시각

## `agent_logs`

Agent 실행과 fallback 기록을 저장한다.

- `id`: UUID primary key
- `session_id`: `survey_sessions.id`
- `question_id`: 관련 질문 id
- `provider`: `mock`, `ollama`, `lmstudio`, `openai`
- `prompt_hash`: prompt 원문 대신 hash
- `request_schema`: JSONB schema metadata
- `raw_response`: 민감정보 mask 후 저장된 provider 응답
- `parsed_result`: JSONB parsed result
- `retry_count`: parse retry 횟수
- `fallback_used`: fallback 사용 여부
- `error_message`: mask 처리된 오류 메시지
- `created_at`: 생성 시각

## `audit_events`

운영 이벤트와 privacy 관련 작업 이력을 저장한다.

- `id`: UUID primary key
- `event_type`: `session_started`, `answer_processed`, `raw_audio_cleanup`, `raw_audio_discarded` 등
- `severity`: `info`, `warning`, `error`
- `session_id`: 관련 session id 또는 null
- `actor_ref`: hash/masked participant reference 또는 null
- `details`: 민감정보를 제외한 JSONB event payload
- `created_at`: 생성 시각

## 개인정보 저장 원칙

Discord user id는 직접 저장하지 않고, 운영에 필요한 경우 hash 또는 masked reference로 저장한다. Orchestrator는 raw `participant_ref`가 들어오면 `PARTICIPANT_HASH_SALT` 기반 hash reference로 정규화한다. raw audio는 DB에 저장하지 않으며 파일 경로와 보관 만료 시각만 저장한다. `SAVE_TRANSCRIPT=false`이면 transcript field는 redacted marker로 저장한다.

## Phase 1 Repository 구현

- Runtime 기본 repository는 `postgres`다.
- Test 전용 repository로 `memory`를 제공한다.
- `REPOSITORY_PROVIDER=postgres|memory`로 선택한다.
- Orchestrator 시작 시 schema 파일을 실행해 필요한 table/index를 보장한다.
- Phase 1 API flow는 `survey_sessions`, `survey_responses`, `agent_logs`를 사용한다.
