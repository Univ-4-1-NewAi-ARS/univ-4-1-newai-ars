# Guardrails

## 개인정보 최소 수집

- 설문 수행에 꼭 필요한 식별자만 저장한다.
- Discord user id는 직접 저장하지 않고 hash 또는 masked reference를 사용한다.
- raw participant id가 Orchestrator API로 직접 들어오면 `PARTICIPANT_HASH_SALT` 기반 hash reference로 정규화한다.
- 세션 분석에 필요하지 않은 프로필, 닉네임, 메시지 내역은 저장하지 않는다.

## 음성 원본 저장 정책

- raw audio 저장 여부는 `SAVE_RAW_AUDIO`로 제어한다.
- raw audio는 DB에 저장하지 않고 파일 경로만 저장한다.
- 보관 기간은 `RAW_AUDIO_RETENTION_DAYS`로 제어한다.
- raw audio 삭제 또는 만료 처리는 `POST /retention/audio/cleanup`으로 수행한다.
- cleanup은 `AUDIO_DIR` 하위 파일만 삭제 대상으로 삼는다.

## Transcript 저장 정책

- transcript 저장 여부는 `SAVE_TRANSCRIPT`로 제어한다.
- 민감정보가 포함될 수 있으므로 report와 log 출력 시 mask 처리한다.
- transcript 보관 기간은 `TRANSCRIPT_RETENTION_DAYS`로 제어한다.
- `SAVE_TRANSCRIPT=false`이면 transcript field는 redacted marker로 저장한다.

## Secret 관리

- `.env`는 절대 commit하지 않는다.
- `.env.example`에는 placeholder만 둔다.
- API key, Discord token, 실제 DB password를 코드, 문서, commit message에 쓰지 않는다.
- 로그에 secret이 포함되면 즉시 mask utility와 테스트를 추가한다.
- provider error message 저장 전 `mask_sensitive_text`를 적용한다.

## Provider Fallback 기록

- local provider 실패 후 API fallback을 사용하면 반드시 로그와 `agent_logs`에 기록한다.
- API fallback은 `.env`에서 허용된 경우만 실행한다.
- provider 미설정 시 시스템이 즉시 죽는 대신 mock/skip/fallback 정책을 따른다.
- fallback 또는 최종 mock 복구가 발생하면 `agent_logs.fallback_used=true`로 남긴다.
