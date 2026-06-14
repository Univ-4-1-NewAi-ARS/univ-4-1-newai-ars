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
- Phase 8: Real Provider Enablement
- Phase 9: Piper Korean TTS Enablement
- Phase 10: Discord Voice Receive

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

## Piper 한국어 TTS

공식 `rhasspy/piper-voices`에는 한국어 voice가 없어 커뮤니티 KSS 모델을 기본 provisioning 대상으로 사용합니다. 모델 바이너리는 저장소에 commit하지 않으며 `models/piper/`로 내려받습니다.

```bash
scripts/provision_piper.sh
# 다른 voice로 교체: PIPER_VOICE_REPO/PIPER_MODEL_FILE/PIPER_CONFIG_FILE 지정
```

provision 후 `.env`에서 `TTS_PROVIDER=local_piper`로 설정하고 `PIPER_MODEL_PATH`가 내려받은 `.onnx` 경로와 일치하는지 확인한 뒤 `scripts/services.sh rebuild tts-service`로 적용합니다. 모델이 없거나 합성이 실패하면 `local_espeak`/`cached_file` fallback이 유지됩니다.

## Discord 음성 응답

실제 음성 답변은 `discord-ext-voice-recv`로 사용자 마이크를 녹음해 STT로 전달합니다.

```text
!survey voice-start          # 음성 채널 입장 + 질문 TTS 재생
!survey voice-listen         # 마이크 녹음 시작, 무음 감지 시 자동 종료 후 STT 제출
!survey voice-file <경로>    # (대체) 미리 준비한 wav 파일로 응답
```

`voice-listen`은 `VOICE_SILENCE_TIMEOUT_SEC` 무음 또는 `VOICE_MAX_RECORD_SEC` 초과 시 녹음을 마치고 `AUDIO_DIR`에 wav를 저장한 뒤 orchestrator로 제출합니다. 녹음된 음성이 없으면 `voice-file`로 안내합니다.

## 주요 문서

- [Project Overview](docs/00_project_overview.md)
- [Architecture](docs/01_architecture.md)
- [Requirements](docs/02_requirements.md)
- [API Spec](docs/03_api_spec.md)
- [Data Model](docs/04_data_model.md)
- [Phase Plan](docs/05_phase_plan.md)
- [Provider Strategy](docs/06_provider_strategy.md)
- [Test Strategy](docs/07_test_strategy.md)
