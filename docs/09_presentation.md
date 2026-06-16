# 발표문 — Discord/전화 기반 한국어 음성 여론조사(ARS) AI 오케스트레이션 플랫폼

> 발표용 스크립트 겸 핸드아웃. 코드 기준으로 작성(2026-06-16).
> 참고 문서: `docs/00_project_overview.md`, `docs/01_architecture.md`,
> `docs/03_api_spec.md`, `docs/06_provider_strategy.md`, `docs/08_telephony_gateway_design.md`.

---

## 1. 간단 요약

이 프로젝트는 **한국어 음성 여론조사(ARS)를 자동으로 진행하는 로컬 AI 오케스트레이션 플랫폼**이다.
질문은 음성으로 들려주고(TTS), 응답은 음성을 받아 글로 옮긴 뒤(STT) LLM이 의미를 분석해 구조화하고,
선택지/감정/키워드 단위로 집계한다. 실제 전화망(ARS)을 붙이기 전에 **Discord 음성 채널을 검증 채널**로
사용해 STT→LLM→TTS→통계 파이프라인을 먼저 완성했다.

**이번 세션의 핵심 발견 — Discord 음성 "수신"이 막혔다.**
Discord는 2026-03-02부터 모든 음성 채널에 **DAVE(종단간 음성 암호화, E2EE)**를 강제했다. 그 결과
들어오는 OPUS 프레임이 암호문이 되어, 현재 어떤 파이썬 Discord 라이브러리도 이를 복호화하지 못한다
(`OpusError: corrupted stream` → 발화의 단편(0.04~0.25s)만 캡처, 오디오 약 99% 손실). **우리 코드나
라이브러리 버전 문제가 아니라 플랫폼 차원의 변경**이다. 더 충격적인 사실은, 이전 스모크에서 보였던
"정확한 전사"가 실제 STT 결과가 아니라 **단편→whisper empty→mock fallback이 파일명(q1/q2/q3)에 맞춰
지어낸 값**이었다는 점이다.

대응으로 두 갈래를 추가했다.
- **난이도가 낮은 하이브리드 모드**: 질문은 음성으로 들려주되(SEND만 사용 → DAVE 무관), 답변은 텍스트로
  받는다. 오늘 바로 동작한다.
- **전화망 게이트웨이(telephony-gateway)**: 원래 로드맵의 최종 목표였던 실제 전화(Twilio)로 설문을 진행한다.
  Orchestrator는 채널 비종속이라 거의 그대로 재사용한다.

또한 데이터 무결성을 위해 **mock의 답변 조작을 차단**(무음이면 답을 지어내지 않고 정직하게 no_speech 반환)하고,
STT에 **VAD + 환각 억제** 디코딩 파라미터를 적용했다.

---

## 2. 프로젝트 구조 (서비스 단위)

전체는 작은 FastAPI 서비스들의 오케스트레이션이다. 핵심 자산은 **채널 비종속 orchestrator**로,
Discord 봇이든 전화 게이트웨이든 동일한 `/sessions`·`/answers` API만 호출하면 STT/LLM/TTS/통계 전 파이프라인을
그대로 재사용한다.

```
        ┌──────────────────────┐        ┌──────────────────────────┐
        │   discord-bot        │        │  telephony-gateway :8300 │
        │  (채널 어댑터 A)      │        │   (채널 어댑터 B, NEW)    │
        │  하이브리드: 질문 TTS │        │  Twilio Programmable     │
        │  재생 + 텍스트 답변   │        │  Voice + <Gather speech> │
        └──────────┬───────────┘        └────────────┬─────────────┘
                   │   동일한 sessions/answers API     │
                   └──────────────┬───────────────────┘
                                  ▼
                    ┌──────────────────────────────┐
                    │   ai-orchestrator  :8000      │
                    │  세션 상태머신 / survey YAML   │
                    │  STT→LLM→TTS 호출 / 통계       │
                    │  PostgreSQL 영속화(asyncpg)    │
                    └───┬───────────┬───────────┬────┘
                        ▼           ▼           ▼
                 stt :8100   (LLM Router)   tts :8200
                 faster-      ollama         espeak /
                 whisper      gemma3:4b      gpt_sovits
                              (host)         cached_file
                                  │
                    ┌─────────────┴─────────────┐
                    │  dashboard :8501           │  postgres :5432 / redis :6379
                    │  요약/의견/헬스/로그        │  ollama, GPT-SoVITS api_v2 (host)
                    └────────────────────────────┘
```

### ai-orchestrator (:8000)
- **역할**: 채널 비종속 세션 상태머신의 두뇌. survey YAML을 로딩하고, 답변마다 STT(필요 시)→LLM 분석→
  결과 저장→다음 질문 TTS를 조율한다. 모든 데이터를 PostgreSQL에 영속화한다.
- **입출력**: 입력은 `POST /sessions`(세션 시작), `POST /sessions/{id}/answers`(transcript 또는 audio_path).
  출력은 `current_question`+`tts`, `agent_result`+`next_question`+`tts`. 조회는 `GET /sessions/{id}/summary`,
  `GET /surveys/{id}/stats`, `GET /surveys/{id}/insights`, `GET /runtime/providers`, `GET /audit/events`.
- **핵심 파일**: `app/main.py`(엔드포인트), `app/services/orchestrator.py`(상태머신),
  `app/providers/llm_router.py`·`app/providers/llm.py`(LLM 라우터),
  `app/providers/speech.py`(STT/TTS HTTP 어댑터), `app/agents/answer_analyzer.py`(LLM→AgentResult),
  `app/models.py`(스키마).

### stt-service (:8100)
- **역할**: 음성→텍스트. 기본 `local_whisper`(faster-whisper small, ko, cpu). VAD로 무음을 잘라내고
  `no_speech_threshold`·`condition_on_previous_text=False`로 **환각(유튜브성 멘트 등)을 억제**한다.
  실패 시 `file` 픽스처→`mock`으로 폴백.
- **무결성**: whisper가 동작했으나 말소리가 없으면 **답을 지어내지 않고** `no_speech=true`를 정직하게 반환한다
  (`stt_fabricate_on_no_speech=false`).
- **입출력**: `POST /transcribe { audio_path, language }` → `{ text, confidence, no_speech, provider, ... }`.
- **핵심 파일**: `app/main.py`.

### tts-service (:8200)
- **역할**: 텍스트→음성. 기본 `local_espeak`(espeak-ng ko). 고품질이 필요하면 `gpt_sovits`(보이스 클로닝)를
  opt-in으로 사용. 모두 실패하면 `TTS_FALLBACK_PROVIDER`→`cached_file`(무음 wav)로 graceful fallback.
- **gpt_sovits**: 호스트에서 네이티브로 도는 GPT-SoVITS `api_v2` 서버(`host.docker.internal:9880`)에
  HTTP로 합성을 요청한다. 참조 오디오+전사로 클론 보이스를 정의(경로는 서버 기준). 2026-06-16 한국어 합성
  라이브 검증 완료.
- **입출력**: `POST /synthesize { text, voice, language, survey_id, question_id }` →
  `{ audio_path, duration_sec, provider, cached, fallback_used }`.
- **핵심 파일**: `app/main.py`.

### discord-bot (채널 어댑터 A)
- **역할**: Discord 명령어 라우팅과 음성 설문 진행. 명령어는
  `!survey start` / `answer` / `voice-start` / `voice-file`.
- **하이브리드 음성 모드(기본, DAVE 우회)**: `voice-start` 시 질문을 TTS로 재생(SEND만)하고, 사용자는
  `!survey answer <답변>`을 **텍스트**로 보낸다. 활성 voice 세션이 있으면 `answer`가 자동으로
  voice 세션의 `submit_text_answer`로 라우팅된다.
- **레거시 오디오 캡처(DAVE 차단)**: `VOICE_ANSWER_MODE=audio`일 때만. `VoiceRecvClient`+`BasicSink`로
  발화 PCM을 캡처하지만 DAVE 때문에 단편만 잡혀 실사용 불가. 코드는 향후 라이브러리 지원 대비용으로 유지.
- **핵심 파일**: `app/main.py`(라우팅, `_voice_survey_loop`), `app/voice_flow.py`(VoiceSurveyManager),
  `app/text_flow.py`(텍스트 설문), `app/orchestrator_client.py`(HTTP 클라이언트).

### dashboard (:8501)
- **역할**: 멀티페이지 운영 대시보드(HTML). orchestrator의 stats/insights/providers/audit를 조회해 시각화.
- **페이지**: `/` 요약(세션·응답 수, 감정 분포, 선택지 집계) / `/insights` 의견 종합(키워드 클라우드, 감정,
  자유응답 인용) / `/services` 서비스 헬스(ping·latency·provider 런타임) / `/logs` 중요 로그(audit_events).
- **핵심 파일**: `app/main.py`.

### telephony-gateway (:8300, 이번 세션 신규)
- **역할**: Discord를 우회해 **실제 전화(Twilio)**로 설문을 진행하는 채널 어댑터. Option A =
  Twilio Programmable Voice + `<Gather input="speech">`로 **Twilio가 STT를 대신 수행**하고, 게이트웨이는
  transcript만 orchestrator에 제출한다.
- **TwiML 흐름**: `POST /voice/incoming`(인바운드 웹훅) → 세션 시작(`channel="phone"`,
  `participant_ref="phone:{발신번호 sha256 12자}"`) → 질문1 `<Say>` + `<Gather>` 반환.
  `POST /voice/answer`(Gather 콜백) → `SpeechResult`를 transcript로 제출 → 다음 질문 `<Say>`+`<Gather>`,
  완료면 완료 멘트 + `<Hangup/>`. per-call 상태는 Twilio `CallSid`로 인메모리 keying.
- **전화 없이 검증**: `scripts/telephony_sim.sh`가 Twilio 폼 페이로드를 흉내내 incoming→answer를 반복 POST하고
  각 단계 TwiML을 출력하며 `<Hangup/>`까지 완주한다(엔드투엔드 PASS). pytest 8 passed.
- **핵심 파일**: `services/telephony-gateway/app/main.py`, `app/orchestrator_client.py`.
  설계: `docs/08_telephony_gateway_design.md`, 작업기록: `log-report/2026-06-16_telephony-gateway-11a.md`.

### 인프라 / 호스트 provider
- **Docker Compose**: postgres(:5432), redis(:6379) + 각 FastAPI 서비스.
- **호스트 네이티브**: ollama(gemma3:4b, :11434), GPT-SoVITS api_v2(:9880, `scripts/gpt_sovits_server.sh`).
  컨테이너는 `host.docker.internal`로 접근한다.

---

## 3. 작동 흐름 (엔드투엔드)

핵심은 **하나의 turn-based 루프**다: 세션 시작 → 첫 질문+TTS → 채널이 질문을 재생/말함 → 답변 수집 →
답변 제출 → orchestrator가 (오디오면 STT +) LLM 분석 → AgentResult 저장 → 다음 질문 또는 완료.

세션 상태머신(`app/services/orchestrator.py`)의 규칙:
- 세션 상태는 `in_progress` → `completed`. 답변 제출 시 세션이 `in_progress`가 아니면 409,
  `question_id` 불일치면 400.
- `needs_retry`이고 `retry_count < max_retry_per_question`이면 **같은 질문을 다시** 묻는다.
- 단, **free_text 질문은 재질문하지 않는다**(`free_text_retry_enabled=false`). 작은 로컬 모델이 정상 답변에
  `needs_retry=true`를 잘못 달아 q2가 무한 반복되던 문제를 막는다.
- 오디오 제출인데 STT가 무음을 감지하면 답을 만들지 않고 **HTTP 422 + audit 이벤트**(`answer_no_speech`)를
  반환 → 채널은 같은 질문을 다시 묻는다.

### (A) Discord 하이브리드 실행
1. 사용자가 음성 채널에서 `!survey voice-start`.
2. 봇이 `POST /sessions`(channel=`discord_voice`) → orchestrator가 q1 + TTS wav 경로 반환.
3. 봇이 **질문을 음성으로 재생**(`FFmpegPCMAudio`), 채팅에 "`!survey answer <답변>`로 답하세요" 안내.
4. 사용자가 `!survey answer 만족합니다` 텍스트 입력. 활성 voice 세션이 있으므로
   `submit_text_answer` → `POST /sessions/{id}/answers { transcript }`.
5. orchestrator: transcript가 있으니 STT 생략 → LLM 분석 → AgentResult 저장 → 다음 질문 q2 + TTS 반환.
6. 봇이 q2를 재생하고 3~5를 반복. 마지막 질문 후 `status="completed"`면 요약 멘트 출력.

### (B) 전화(Twilio) 실행
1. 발신자가 Twilio 번호로 전화 → Twilio가 `POST /voice/incoming` 웹훅 호출.
2. 게이트웨이가 `POST /sessions`(channel=`phone`) → q1 + TTS. TwiML로 q1 `<Say ko-KR>` +
   `<Gather input="speech" action="/voice/answer">` 반환.
3. 발신자가 음성으로 답함 → **Twilio가 STT 수행** → `SpeechResult`를 `POST /voice/answer`로 전달.
4. 게이트웨이가 transcript를 `POST /sessions/{id}/answers`로 제출 → orchestrator가 LLM 분석 →
   다음 질문 반환. 게이트웨이는 다음 질문 `<Say>`+`<Gather>` 또는 완료면 완료 멘트 + `<Hangup/>` 반환.
5. 빈 `SpeechResult`면 같은 질문 재요청, 알 수 없는 CallSid/오류면 안내 후 `<Hangup/>`(발신자를 방치하지 않음).

두 경로 모두 **동일한 orchestrator 코드 경로**를 탄다. 차이는 STT 주체뿐이다(하이브리드=텍스트라 STT 불필요,
전화 Option A=Twilio 클라우드 STT). audio_path 경로를 쓰면 로컬 whisper가 동작하며 no-speech 무결성도 동일 적용.

---

## 4. 사용 프롬프트

답변 분석은 `app/agents/answer_analyzer.py`의 `_build_prompt`가 만든 **JSON task contract**로 이뤄진다.
LLM에 질문 정의와 transcript를 함께 주고, `AgentResult` 스키마에 맞는 **JSON 하나만** 돌려받는다.

```jsonc
{
  "task": "analyze_survey_answer",
  "instructions": [
    "Return only one JSON object. Do not include markdown or explanatory text.",
    "The JSON object must validate against the AgentResult schema.",
    "For single_choice questions, selected_option must be one of the configured option ids or null.",
    "For single_choice, set needs_retry=true only when the answer matches no option.",
    "For free_text, any non-empty opinion is acceptable: set needs_retry=false unless the transcript is empty or unintelligible."
  ],
  "schema_name": "AgentResult",
  "required_fields": {
    "question_id": "string",
    "raw_transcript": "string",
    "cleaned_text": "string",
    "answer_type": "single_choice or free_text",
    "selected_option": "string option id or null",
    "confidence": "number between 0 and 1",
    "sentiment": "positive, neutral, negative, or unknown",
    "keywords": "array of short strings",
    "needs_retry": "boolean",
    "review_required": "boolean",
    "reason": "short string"
  },
  "question": { /* survey YAML의 질문 정의(options 포함) */ },
  "transcript": "<사용자 답변 텍스트>"
}
```

핵심 계약 포인트:
- **single_choice**: `selected_option`은 설정된 option id 중 하나이거나 null. 답이 어떤 옵션에도 매칭되지
  않을 때만 `needs_retry=true`.
- **free_text**: 비어있지 않은 의견은 모두 수용 → `needs_retry=false`(빈/판독불가일 때만 true). 이 규칙과
  상태머신의 free_text 무재질문 정책이 맞물려 자유응답 루프를 막는다.

**Provider 라우터**(`app/providers/llm_router.py` / `llm.py`):
1차 `ollama`(gemma3:4b, `host.docker.internal:11434`, `format:"json"`) → API fallback `OpenAI`
(`response_format: json_object`) → 최종 `mock`. 각 provider 응답은 `AgentResult.model_validate`로
구조 검증하고, 파싱 실패 시 `llm_parse_retry_count`만큼 재시도한 뒤 다음 provider로 넘어간다. `ProviderUnavailable`이면
즉시 다음 provider로 폴백한다(`answer_analyzer.analyze_answer`).

---

## 5. 에이전트(대화) 흐름

여기서 "에이전트"는 orchestrator가 주도하는 **턴 기반 대화 진행자**다: 질문을 던지고 → 사용자 답을 받고 →
LLM이 `AgentResult`를 만들고 → 재질문/다음/완료를 결정한다. 설문은
`surveys/campus_opinion_survey.yaml`(q1: single_choice, q2·q3: free_text)을 사용한다.

예시 대화:

```
에이전트(q1, 음성): 현재 캠퍼스 시설에 얼마나 만족하시나요?
                    (옵션: 1 매우 만족 / 2 만족 / 3 보통 / 4 불만족)
사용자:            만족합니다.

에이전트(q2, 음성): 가장 개선이 필요한 영역은 무엇인가요?
사용자:            도서관 좌석이 더 필요합니다.

에이전트(q3, 음성): 향후 캠퍼스 운영에 대한 전반적인 의견을 말씀해 주세요.
사용자:            전반적으로 좋습니다.
에이전트:          응답해 주셔서 감사합니다. 설문이 완료되었습니다.
```

q1(single_choice) 답변 "만족합니다"에 대한 `AgentResult`(예):

```json
{
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
  "reason": "Transcript matched option 2."
}
```

q2(free_text) 답변 "도서관 좌석이 더 필요합니다"에 대한 `AgentResult`(예):

```json
{
  "question_id": "q2",
  "raw_transcript": "도서관 좌석이 더 필요합니다",
  "cleaned_text": "도서관 좌석이 더 필요합니다",
  "answer_type": "free_text",
  "selected_option": null,
  "confidence": 0.75,
  "sentiment": "positive",
  "keywords": ["도서관", "좌석", "필요합니다"],
  "needs_retry": false,
  "review_required": false,
  "reason": "Free-text answer accepted."
}
```

이렇게 저장된 `selected_option`/`sentiment`/`keywords`는 **대시보드 `/insights`에서 집계**된다:
single_choice는 옵션별 비율 막대, free_text는 키워드 클라우드 + 감정 색상으로 표시된 자유 의견 인용으로
한눈에 여론을 본다(`get_survey_insights`가 질문별·전체로 sentiment/keyword를 합산).

---

## 6. 향후 계획 / 로드맵

전화망을 중심으로 한 단계적 확장(설계는 `docs/08`):

- **11a — Telephony Option A (완료)**: Twilio Programmable Voice + `<Gather speech>`.
  전화 없이 `scripts/telephony_sim.sh`로 엔드투엔드 검증, pytest 8 passed. 남은 일은 실 Twilio 번호 + 공개
  HTTPS(ngrok) 스모크.
- **11b — Twilio Media Streams + 로컬 whisper (권장 타깃)**: `<Connect><Stream>`로 오디오를 받아
  μ-law→16k 변환 후 **로컬 whisper로 STT** → 오디오를 클라우드 STT에 넘기지 않아 프라이버시 회복 +
  기존 provider/no-speech 무결성 재사용.
- **11c — 자체 호스팅 SIP(Asterisk/FreeSWITCH)**: 완전 로컬·사설, 분당 STT 비용 없음. 인프라 최중량.
- **TTS 품질**: 현재 GPT-SoVITS 참조 음성은 espeak 생성(임시) → **실제 한국어 음성 클립**으로 교체해 자연스러운
  목소리 확보.
- **Discord 오디오**: 파이썬 라이브러리가 **DAVE 수신 복호화를 지원**하면 레거시 audio 캡처 경로를 재검토.
  그 전까지 전화망이 음성 응답의 최우선 경로.
```
