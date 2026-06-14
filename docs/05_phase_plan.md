# Phase Plan

## Phase 0 — Repository Bootstrap & Documentation Foundation

- 목표: 디렉터리 구조, 핵심 docs, rules, `.env.example`, Docker Compose skeleton, README 작성
- 산출물: docs/rules/material/log 디렉터리, compose skeleton, sample survey
- 테스트 기준: `docker compose config`, git 상태 확인
- 완료 조건: report/done 기록과 git commit

## Phase 1 — Orchestrator Core with Text/Mock Flow

- 목표: FastAPI Orchestrator, survey YAML loader, session state machine, mock STT/TTS/LLM, repository 구현
- 산출물: `/health`, session/answer API, PostgreSQL init schema, pytest
- 테스트 기준: transcript 제출 시 session/response 저장
- 완료 조건: API 문서 갱신, pytest 통과, report/done/commit
- 상태: pytest 통과, Docker runtime smoke 완료(2026-06-15): `/health`, `/sessions`, `/sessions/{id}/answers`, `/sessions/{id}/summary`, `/surveys/{id}/stats` 검증

## Phase 2 — Provider Router & Structured Output

- 목표: LLM provider router, Ollama/LM Studio/OpenAI skeleton, structured output validation, retry/fallback policy
- 산출물: agent module, Pydantic schema, provider 선택 테스트
- 테스트 기준: `.env` 변경으로 mock provider 선택, graceful skip
- 완료 조건: agent result JSONB 저장, report/done/commit
- 상태: pytest 통과, Docker runtime smoke 완료(2026-06-15): LLM router, structured output, provider fallback 검증

## Phase 3 — STT/TTS Services

- 목표: STT/TTS FastAPI 서비스, mock/file provider, cached TTS 전략
- 산출물: `/transcribe`, `/synthesize`, service-level tests
- 테스트 기준: Orchestrator가 STT/TTS service와 통신 가능
- 완료 조건: mock audio/transcript flow, report/done/commit
- 상태: pytest 통과, Docker runtime smoke 완료(2026-06-15): `/transcribe`(local_whisper fallback), `/synthesize`(local_espeak, fallback_used=false) 검증

## Phase 4 — Discord Bot Text Mode

- 목표: Discord Bot 연결과 text command 기반 설문
- 산출물: `/survey start`, text answer flow, Discord summary
- 테스트 기준: token 없을 때 mock mode, token 있을 때 text flow
- 완료 조건: report/done/commit
- 상태: pytest 통과, Docker image 빌드 완료(2026-06-15). 실제 Discord token 수동 검증 pending(환경 외 자산)

## Phase 5 — Discord Voice MVP

- 목표: voice channel join, cached TTS 재생, 음성 또는 파일 기반 응답 수집
- 산출물: voice gateway implementation 또는 stable mock/file fallback
- 테스트 기준: 최소 1개 질문 closed loop
- 완료 조건: transcript 분석 저장, 다음 질문/종료 처리, report/done/commit
- 상태: voice join/play skeleton 및 file-based audio answer fallback 구현

## Phase 6 — Stats Dashboard & Reports

- 목표: stats endpoint, dashboard, Markdown report exporter
- 산출물: 통계 API, report output, dashboard view
- 테스트 기준: 응답 수, 선택지 비율, sentiment 분포 조회
- 완료 조건: report/done/commit
- 상태: stats endpoint, Markdown report exporter, FastAPI dashboard 구현

## Phase 7 — Hardening & Privacy

- 목표: audit log, error handling, privacy mask, retention config, security docs 강화
- 산출물: 실패/복구 테스트, privacy utility, audit log policy
- 테스트 기준: 민감정보 로그 노출 방지와 fallback 기록 검증
- 완료 조건: report/done/commit
- 상태: privacy mask utility, participant hash normalization, audit events, raw audio retention cleanup 구현

## Phase 8 — Real Provider Enablement

- 목표: 기본 mock 해제, local real provider 우선 실행, 유연한 fallback 유지
- 산출물: Ollama runtime path, local Whisper STT, local espeak/Piper TTS, provider status endpoint
- 테스트 기준: Ollama provider 기록, local_whisper STT smoke, local_espeak TTS smoke, fallback 기록 검증
- 완료 조건: docs/report/done 갱신, pytest와 Docker runtime smoke 통과, commit
- 상태: Ollama `gemma3:4b`, `local_whisper`, `local_espeak` runtime 검증 완료

## Phase 9 — Piper Korean TTS Enablement

- 목표: `local_piper` 실경로 활성화, 한국어 voice 모델 provisioning, espeak/cached fallback 유지
- 산출물: `scripts/provision_piper.sh`, `tts-service`에 `piper-tts` CLI 설치, KR 모델 기본 경로, piper 성공 경로 테스트, docs 갱신
- 테스트 기준: `local_piper` 성공 시 provider-specific wav 생성과 `fallback_used=false`, 모델 부재 시 fallback 기록
- 완료 조건: pytest 통과, docs/report/done 갱신, commit
- 상태: `local_espeak`(espeak-ng)가 한국어 working TTS. `piper-tts` pip 패키지는 `espeak/text/pinyin` phoneme type만 지원, KSS 한국어 모델(`pygoruut` type)과 구조적 비호환 확인. `piper-tts` dep 제거, `local_piper` 경로는 유지(호환 모델 또는 컴파일 바이너리 용). `provision_piper.sh`가 phoneme type 호환성을 검증 후 경고 출력하도록 강화. TTS pytest 5 passed.

## Phase 10 — Discord Voice Receive

- 목표: file 기반 fallback을 넘어 실제 Discord 음성 입력을 캡처해 STT로 전달
- 산출물: `discord-ext-voice-recv` 기반 `VoiceRecvClient` 연결, `VoiceRecorder` PCM 버퍼/wav 인코더, `!survey voice-listen` 명령, silence 기반 auto-stop
- 테스트 기준: PCM feed → wav round-trip, silence/no-audio 시 capture loop 동작
- 완료 조건: pytest 통과, docs/report/done 갱신, commit
- 상태: `VoiceRecorder`(48k stereo PCM 버퍼 + 16kHz mono 다운믹스 wav 출력)와 capture loop 단위 테스트 통과(11 passed). 실제 Discord voice receive runtime smoke는 token + voice channel 필요로 수동 검증 pending
