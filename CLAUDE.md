# CLAUDE.md — discord-ars-survey-agent

다음 세션에서 이 파일을 읽으면 프로젝트 전체 흐름을 파악할 수 있다.

---

## 프로젝트 한 줄 요약

Discord Voice Channel을 전화 ARS 대체 채널로 사용해 음성 여론조사 흐름을 검증하는 로컬 AI 오케스트레이션 플랫폼. 실제 전화망 연동 전 STT/LLM/TTS/통계 파이프라인을 Discord에서 검증한다.

---

## 아키텍처

```
Discord Bot
  │  !survey voice-start  →  voice-survey loop (asyncio task)
  │      TTS 재생 (FFmpegPCMAudio, await finish)
  │      VoiceRecvClient + BasicSink → PCM 캡처
  │      48kHz stereo → 16kHz mono wav 다운믹스
  │      submit_audio_file → Orchestrator
  │
  └──→ AI Orchestrator (FastAPI :8000)
         survey YAML 로딩, 세션 상태 머신
         STT Service (HTTP) → LLM Router → AgentResult
         TTS Service (HTTP) → wav 경로
         PostgreSQL 저장 (asyncpg)
         │
         ├── STT Service (:8100) — faster-whisper local_whisper / file / mock
         ├── TTS Service (:8200) — espeak-ng local_espeak / cached_file
         └── Dashboard (:8501) — FastAPI stats view

인프라: postgres, redis (Docker Compose)
```

---

## 서비스별 포트 및 핵심 엔드포인트

| 서비스 | 포트 | 핵심 엔드포인트 |
|---|---|---|
| ai-orchestrator | 8000 | `POST /sessions`, `POST /sessions/{id}/answers`, `GET /sessions/{id}/summary`, `GET /surveys/{id}/stats`, `GET /surveys/{id}/insights`, `GET /runtime/providers`, `GET /audit/events` |
| stt-service | 8100 | `POST /transcribe` |
| tts-service | 8200 | `POST /synthesize` |
| dashboard | 8501 | `GET /` 요약, `GET /insights` 의견 종합, `GET /services` 서비스 헬스, `GET /logs` 중요 로그 (profile: dashboard) |
| postgres | 5432 | — |
| redis | 6379 | — |

---

## Provider 현황

| 레이어 | 기본값 | fallback |
|---|---|---|
| LLM | `ollama` (gemma3:4b, host.docker.internal:11434) | OpenAI API → mock |
| STT | `local_whisper` (faster-whisper small, ko, cpu, VAD+anti-hallucination) | file fixture → mock. 무음 시 조작 안 함(no_speech) |
| TTS | `local_espeak` (espeak-ng ko) / `gpt_sovits`(voice-clone, opt-in) | TTS_FALLBACK_PROVIDER → cached_file |

**중요 — Piper KR**: `piper-tts` pip 패키지는 `espeak/text/pinyin` phoneme만 지원. 커뮤니티 KSS 한국어 모델(`neurlang/piper-onnx-kss-korean`)은 `pygoruut` type → 구조적 비호환. `local_espeak`가 실사용 한국어 TTS. `local_piper` 코드 경로는 남아 있어 향후 호환 모델 사용 가능.

**GPT-SoVITS TTS**: `TTS_PROVIDER=gpt_sovits`로 활성. GPT-SoVITS `api_v2` 서버(기본 `host.docker.internal:9880`) 필요. `GPT_SOVITS_REF_AUDIO_PATH`/`REF_TEXT`로 클론할 목소리 지정(경로는 GPT-SoVITS 서버 기준). 서버 부재/미설정 시 fallback chain으로 graceful 처리. primary로 쓸 땐 `TTS_FALLBACK_PROVIDER=local_espeak` 권장(무음 대신 실음성).

---

## Discord 봇 명령어

```
!survey start [survey_id]        — 텍스트 설문 시작
!survey answer <text>            — 텍스트 응답 제출
!survey voice-start [survey_id]  — 음성 설문 시작 (자동 루프)
!survey voice-file <path>        — 파일 경로로 수동 응답 (fallback)
```

**voice-start 흐름 (Phase 10 자동 루프)**:
1. `VoiceRecvClient`로 연결 (play + capture 동시 가능)
2. 질문 TTS 재생 → `await done` (after= callback으로 완료 대기)
3. `BasicSink`로 발화자 PCM 캡처
4. 무음 `VOICE_SILENCE_TIMEOUT_SEC`초 또는 최대 `VOICE_MAX_RECORD_SEC`초 후 종료
5. 48kHz stereo → 16kHz mono 다운믹스 wav 저장 (`/data/audio/`)
6. Orchestrator 제출 → STT → LLM → 다음 질문 TTS → 3번으로 반복
7. 설문 완료 또는 빈 캡처 3회 시 종료 후 disconnect

---

## Phase 상태 (2026-06-15 기준)

| Phase | 내용 | 상태 |
|---|---|---|
| 0 | Repository Bootstrap | ✅ 완료 |
| 1 | Orchestrator Core | ✅ pytest + Docker smoke 완료 |
| 2 | Provider Router & Structured Output | ✅ pytest + Docker smoke 완료 |
| 3 | STT/TTS Services | ✅ pytest + Docker smoke 완료 |
| 4 | Discord Bot Text Mode | ✅ pytest + Docker image 빌드. Discord token 수동 pending |
| 5 | Discord Voice MVP | ✅ skeleton + file fallback 구현 |
| 6 | Stats Dashboard & Reports | ✅ stats endpoint + Markdown report + dashboard |
| 7 | Hardening & Privacy | ✅ privacy mask, audit log, retention |
| 8 | Real Provider Enablement | ✅ Ollama, local_whisper, local_espeak runtime 검증 |
| 9 | Piper KR TTS | ⚠️ local_espeak 동작, piper pygoruut 비호환 문서화 |
| 10 | Discord Voice Receive | ✅ 실발화 스모크 완료(2026-06-16). 음성 설문 2건 엔드투엔드 완주(TTS→캡처→STT→LLM→다음질문→완료). 실 전사 정확("만족합니다"/"도서관 좌석이 더 필요합니다"/"전반적으로 좋습니다"). 잔여 품질 이슈는 알려진 이슈 참조 |

---

## Pytest 현황 (2026-06-16)

```
ai-orchestrator  22 passed   (+audit/events, +insights, +retry policy, +no_speech)
stt-service       7 passed   (+VAD kwargs, +no_speech)
tts-service       8 passed   (+gpt_sovits x3)
discord-bot      13 passed   (+no_speech signal, +client 422)
dashboard         6 passed   (+services/logs/nav, +insights pages)
총               56 passed, 0 failed
```

주의: orchestrator 테스트는 `LLM_PROVIDER=mock` 강제 필요. Docker에서 실행 시
`host.docker.internal:11434` 실 ollama에 도달해 `test_text_flow`가 비결정적으로
실패할 수 있다(컨테이너 실행: `docker run -e LLM_PROVIDER=mock ...`).

로컬 venv 주의: 동기화된 `.venv`는 macOS aarch64용 — Windows에서 실행 불가.
임시 venv: `python -m venv %TEMP%\arsvenv && %TEMP%\arsvenv\Scripts\pip install fastapi pydantic pydantic-settings httpx pytest pytest-asyncio PyYAML asyncpg`

---

## Docker 실행

```bash
# 전체 핵심 서비스 실행
scripts/services.sh on core

# 개별 재빌드
scripts/services.sh rebuild discord-bot

# 상태 확인
scripts/services.sh status

# 헬스체크
curl http://localhost:8000/health
curl http://localhost:8100/health
curl http://localhost:8200/health
curl http://localhost:8000/runtime/providers
```

`.env`가 없으면 `.env.example`을 복사: `cp .env.example .env`

---

## 알려진 이슈 / 다음 작업 후보

1. **🚫 Discord 음성 수신 = DAVE E2EE로 업스트림 차단 (2026-06-16 확정)**:
   - **Discord가 2026-03-02부터 모든 음성 채널에 DAVE(종단간 암호화)를 강제**. OPUS 프레임이 AES128-GCM E2E 암호화됨.
   - `discord-ext-voice-recv`(및 py-cord)는 **DAVE 수신 복호화 미구현** → 수신 opus가 암호문 → `OpusError: corrupted stream` → 0.04~0.25s 단편만 캡처(오디오 ~99% 손실). **우리 코드/라이브러리 버전 문제 아님.**
   - **충격적 사실**: 이전 스모크의 "정확한 전사"는 실제 STT가 아니라 **단편→whisper empty→mock fallback이 q1/q2/q3 파일명에 맞춰 지어낸 값**. 실 음성 답변은 아직 못 받고 있었음.
   - 대응: Task 2로 mock 조작 차단(무결성), 캡처는 Python 라이브러리의 DAVE 수신 지원 대기 또는 **계획된 SIP/Twilio 전화망 채널로 전환**(Discord 우회 — 원래 로드맵의 최종 목표).
   - 부수 수정 완료: `needs_retry` free_text 무시(q2 3회 루프 해결), STT VAD anti-hallucination, `ORCHESTRATOR_TIMEOUT_SEC=120`.
2. **Piper KR 모델**: `espeak` phoneme type 한국어 piper 모델 탐색 또는 직접 학습
3. **STT 정확도/환각**: 발화자 accent/noise 테스트, whisper beam_size/VAD 조정 검토. `/insights`에서 무음·잡음 구간 Whisper 환각("Please subscribe, like, and comment." 등 유튜브성 문구) 관측됨 → VAD(`vad_filter`) 또는 `no_speech_threshold` 적용 후보
4. **Dashboard**: ✅ 멀티페이지 재구성 완료(2026-06-16). `/` 요약 + `/insights` 의견 종합(키워드 클라우드/감정/자유응답 의견) + `/services` 서비스 헬스(ping/latency/provider) + `/logs` 중요 로그(audit_events). orchestrator에 `GET /audit/events`, `GET /surveys/{id}/insights` 추가. dashboard pytest 6 passed
5. **전화망 확장**: SIP/Twilio gateway → Orchestrator 연결 (현재 아키텍처에서 Discord bot만 교체)

---

## 규칙 참조

- `rules/codex_workflow_rules.md` — phase 단위 작업, log-report/log-done 기록 의무
- `rules/commit_rules.md` — `.env` stage 금지, test 후 commit
- `rules/env_rules.md` — provider 설정, 모델 자산 commit 금지
- `rules/coding_convention.md` — Python 코딩 스타일
- `rules/guardrails.md` — privacy/security 가이드라인

---

## 핵심 파일 위치

```
services/
  ai-orchestrator/app/
    main.py              — FastAPI app, 모든 엔드포인트
    services/orchestrator.py — 세션 상태머신, STT/TTS/LLM 호출
    providers/llm_router.py  — Ollama/OpenAI/mock 라우터
    providers/speech.py      — STT/TTS HTTP adapter
    core/settings.py         — 모든 env 설정
    agents/answer_analyzer.py — LLM → AgentResult
  discord-bot/app/
    main.py              — 명령어 라우팅, _voice_survey_loop
    voice_flow.py        — VoiceSurveyManager (session state)
    voice_recorder.py    — PCM 버퍼, 48k→16k 다운믹스, wav 출력
    text_flow.py         — 텍스트 설문 매니저
    orchestrator_client.py — HTTP client to ai-orchestrator
  stt-service/app/main.py  — /transcribe, local_whisper/file/mock
  tts-service/app/main.py  — /synthesize, local_espeak/local_piper/cached_file
  dashboard/app/main.py    — /stats view

scripts/
  services.sh            — Docker Compose 서비스 제어
  provision_piper.sh     — Piper voice 모델 다운로드 + phoneme 호환성 검증

surveys/campus_opinion_survey.yaml — 기본 설문 예시

docs/
  05_phase_plan.md       — 전체 phase 계획 및 상태
  06_provider_strategy.md — STT/TTS/LLM provider 전략 상세
  03_api_spec.md         — API 명세
```
