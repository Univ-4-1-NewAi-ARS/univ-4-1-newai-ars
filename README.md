# discord-ars-survey-agent

Discord Voice를 전화망 대체 입력 채널로 사용해 ARS 여론조사 흐름을 검증하는 로컬 우선 AI 오케스트레이션 프로젝트입니다.

이 저장소는 장기 개발을 전제로 phase 단위로 진행합니다. 각 phase는 문서 갱신, 구현, 테스트, 검증 보고서, 완료 기록, git commit을 포함합니다.

## MVP 방향

- Discord Bot 또는 mock client로 설문 세션 시작
- TTS 또는 cached audio로 질문 출력
- 음성 또는 텍스트 응답을 STT/mock STT로 transcript화
- AI Orchestrator가 설문 상태를 진행하고 structured JSON으로 응답 분석
- PostgreSQL에 세션/응답/agent 로그 저장
- 통계 조회 및 Markdown 보고서 생성

## Phase 상태

- Phase 0: Repository Bootstrap & Documentation Foundation
- Phase 1: Orchestrator Core with Text/Mock Flow
- Phase 2: Provider Router & Structured Output
- Phase 3: STT/TTS Services
- Phase 4: Discord Bot Text Mode
- Phase 5: Discord Voice MVP
- Phase 6: Stats Dashboard & Reports
- Phase 7: Hardening & Privacy

## 개발 환경

- Python 3.11+
- Docker Desktop
- PostgreSQL
- Redis
- macOS host native Ollama 또는 LM Studio 권장

로컬 모델은 컨테이너 밖에서 실행하고, 컨테이너 내부에서는 `host.docker.internal`로 접근하는 구성을 기본으로 합니다.

## 빠른 검증

```bash
cp .env.example .env
docker compose config
```

Phase 0에서는 서비스 구현이 아직 없으므로 compose는 skeleton validation 기준입니다.

## 서비스 제어

개별 Docker Compose 서비스를 켜고 끌 때는 `scripts/services.sh`를 사용합니다.

```bash
scripts/services.sh on core
scripts/services.sh off dashboard
scripts/services.sh rebuild discord-bot
scripts/services.sh status
```

지원 서비스는 `postgres`, `redis`, `ai-orchestrator`, `stt-service`, `tts-service`, `discord-bot`, `dashboard`, `adminer`입니다.

## Mock 해제 기본 설정

실제 provider를 우선 사용하고 장애 시 fallback을 유지하려면 `.env`를 다음 방향으로 설정합니다.

```env
DISCORD_MOCK_MODE=false
LLM_PROVIDER=ollama
LLM_MODEL=gemma3:4b
LLM_USE_MOCK_FALLBACK=true
STT_PROVIDER=local_whisper
STT_USE_MOCK_FALLBACK=true
TTS_PROVIDER=local_espeak
TTS_FALLBACK_PROVIDER=cached_file
TTS_USE_CACHED_FALLBACK=true
```

적용 후:

```bash
scripts/services.sh rebuild stt-service tts-service ai-orchestrator discord-bot
curl http://localhost:8000/runtime/providers
```

## 주요 문서

- [Project Overview](docs/00_project_overview.md)
- [Architecture](docs/01_architecture.md)
- [Requirements](docs/02_requirements.md)
- [API Spec](docs/03_api_spec.md)
- [Data Model](docs/04_data_model.md)
- [Phase Plan](docs/05_phase_plan.md)
- [Provider Strategy](docs/06_provider_strategy.md)
- [Test Strategy](docs/07_test_strategy.md)
