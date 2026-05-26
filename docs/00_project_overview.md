# Project Overview

## 프로젝트 목적

`discord-ars-survey-agent`는 전화 ARS 여론조사 시스템을 실제 전화망 없이 검증하기 위한 테스트/시뮬레이션 플랫폼이다. Discord Voice Channel을 임시 음성 입출력 채널로 사용하고, Python 기반 AI Orchestrator가 STT, Agent 분석, 통계 저장, TTS 응답, 보고서 생성을 단계적으로 수행한다.

## 도메인 정의

대상 도메인은 음성 기반 자동 여론조사다. 사용자는 질문을 듣고 음성 또는 텍스트로 응답하며, 시스템은 응답을 구조화된 데이터로 변환해 저장하고 다음 질문 또는 종료를 결정한다.

## 전화 ARS와 Discord 테스트 버전의 관계

Discord 버전은 전화망의 IVR/ARS 채널을 대체하는 실험용 gateway다. 실제 전화망 연동 전 다음 요소를 먼저 검증한다.

- 질문 재생과 응답 수집 흐름
- STT 결과를 기반으로 한 응답 해석
- 설문 상태 머신
- 구조화된 agent output
- 통계 저장과 보고서 생성
- provider 교체 및 fallback 정책

향후 전화망 확장 시 Discord Voice Gateway를 SIP/전화 provider gateway로 교체하는 것을 목표로 한다.

## 주요 사용자 시나리오

1. 운영자가 설문 YAML을 등록한다.
2. Discord 사용자가 음성 채널에 입장하거나 text command로 설문을 시작한다.
3. Bot이 질문을 TTS 또는 cached audio로 재생한다.
4. 사용자가 음성 또는 텍스트로 답변한다.
5. STT provider가 transcript를 생성한다.
6. AI Orchestrator가 응답을 분석하고 다음 질문을 결정한다.
7. 모든 질문이 끝나면 통계와 요약 보고서가 생성된다.
8. Discord text channel 또는 dashboard에 요약이 표시된다.

## MVP 범위

- Docker Compose 기반 skeleton
- mock provider 기반 closed-loop 설계
- 설문 정의 YAML
- Orchestrator API 설계
- PostgreSQL 중심 data model 설계
- STT/TTS/LLM provider interface와 router 설계
- phase별 구현/검증/보고 체계

## 제외 범위

- 실제 전화망 연동
- 결제/CRM/콜센터 시스템 연동
- 대규모 동시 통화 처리
- 완전한 실시간 streaming STT
- 개인정보 동의 관리 UI
- 운영용 보안 hardening

## 향후 전화망 확장 방향

Discord Voice Gateway를 별도 interface로 유지하고, 이후 SIP trunk, Twilio, Asterisk, FreeSWITCH 같은 전화망 gateway를 추가한다. Orchestrator, provider router, repository, report exporter는 전화망과 독립적으로 유지한다.
