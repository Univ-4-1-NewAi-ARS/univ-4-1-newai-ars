# Requirements

## Functional Requirements

- 설문 정의를 YAML에서 로드할 수 있어야 한다.
- Discord text 또는 voice gateway로 설문 세션을 시작할 수 있어야 한다.
- 각 세션은 현재 질문, retry count, 완료 상태를 추적해야 한다.
- 음성 응답은 STT provider를 통해 transcript로 변환되어야 한다.
- 텍스트 응답은 mock/text flow에서 직접 처리할 수 있어야 한다.
- Agent 분석 결과는 Pydantic schema로 검증된 JSON이어야 한다.
- 분석 결과와 원본 transcript는 정책에 따라 PostgreSQL에 저장되어야 한다.
- 모든 질문 완료 후 통계와 Markdown 보고서를 생성할 수 있어야 한다.
- Provider는 `.env` 변경만으로 교체 가능해야 한다.

## Non-Functional Requirements

- Python 3.11 이상을 기준으로 한다.
- Docker Compose로 주요 서비스를 실행할 수 있어야 한다.
- Apple Silicon M4 Mac mini 16GB 환경에서 local-first로 동작해야 한다.
- 7B~8B quantized local LLM 사용을 우선 고려한다.
- 초기 phase는 파일 단위 또는 semi-streaming 처리를 허용한다.
- provider 장애 시 mock/skip/fallback 경로를 명확히 기록해야 한다.

## Privacy and Security Requirements

- `.env`는 commit하지 않는다.
- API key, Discord token, 실제 DB password는 코드와 문서에 기록하지 않는다.
- Discord user id는 운영상 필요한 최소 범위로 저장한다.
- raw audio 저장 여부는 `SAVE_RAW_AUDIO`로 제어한다.
- transcript 저장 여부는 `SAVE_TRANSCRIPT`로 제어한다.
- 민감정보는 로그와 report에서 mask 처리한다.
- raw audio는 DB에 binary로 넣지 않고 파일 경로만 저장한다.

## Local-First Requirements

- LLM은 Ollama 또는 LM Studio host native 실행을 우선한다.
- STT는 local Whisper 계열을 우선하되 초기 phase에서는 mock/file provider를 사용한다.
- TTS는 cached wav 또는 local TTS를 우선한다.
- OpenAI 등 API provider는 fallback 또는 검증용으로만 사용한다.
- fallback 사용 여부는 `.env`로 켜고 끌 수 있어야 한다.

## Docker and Runtime Requirements

- 기본 서비스는 `discord-bot`, `ai-orchestrator`, `postgres`, `redis`, `stt-service`, `tts-service`다.
- `dashboard`, `adminer`는 profile 기반 선택 서비스로 둔다.
- 컨테이너에서 host native LLM은 `host.docker.internal`로 접근한다.
- `docker compose config`가 통과해야 한다.
- Phase 1 이후 `/health` endpoint가 통과해야 한다.
