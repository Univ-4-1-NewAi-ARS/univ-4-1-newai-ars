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
- 상태: 로컬 pytest/API 검증 완료, Docker daemon 비활성으로 compose runtime smoke pending

## Phase 2 — Provider Router & Structured Output

- 목표: LLM provider router, Ollama/LM Studio/OpenAI skeleton, structured output validation, retry/fallback policy
- 산출물: agent module, Pydantic schema, provider 선택 테스트
- 테스트 기준: `.env` 변경으로 mock provider 선택, graceful skip
- 완료 조건: agent result JSONB 저장, report/done/commit
- 상태: 로컬 pytest 검증 완료, Docker runtime smoke pending

## Phase 3 — STT/TTS Services

- 목표: STT/TTS FastAPI 서비스, mock/file provider, cached TTS 전략
- 산출물: `/transcribe`, `/synthesize`, service-level tests
- 테스트 기준: Orchestrator가 STT/TTS service와 통신 가능
- 완료 조건: mock audio/transcript flow, report/done/commit
- 상태: 로컬 pytest와 HTTP adapter mock 검증 완료, Docker runtime smoke pending

## Phase 4 — Discord Bot Text Mode

- 목표: Discord Bot 연결과 text command 기반 설문
- 산출물: `/survey start`, text answer flow, Discord summary
- 테스트 기준: token 없을 때 mock mode, token 있을 때 text flow
- 완료 조건: report/done/commit
- 상태: tokenless mock mode와 text flow client 로컬 테스트 완료, 실제 Discord token 수동 검증 pending

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
