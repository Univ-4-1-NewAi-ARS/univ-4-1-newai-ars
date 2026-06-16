# 실 사용 매뉴얼 — Discord/전화 음성 여론조사(ARS) 플랫폼

> 실제 운영·시연 기준 사용법. 2026-06-16 검증 기준.
> 채널은 두 가지: **Discord 하이브리드**(오늘 동작) / **전화(Twilio)**(이 문서의 스모크 대상).

---

## 0. 구성 요소 한눈에

| 구성 | 위치 | 포트 | 비고 |
|---|---|---|---|
| ai-orchestrator | Docker | 8000 | 세션 상태머신, 채널 비종속 |
| stt-service | Docker | 8100 | faster-whisper (전화 Option A에선 미사용) |
| tts-service | Docker | 8200 | espeak / gpt_sovits |
| discord-bot | Docker | — | 하이브리드 음성 설문 |
| telephony-gateway | Docker | 8300 | Twilio 전화 설문 (Option A) |
| dashboard | Docker | 8501 | 요약/의견/헬스/로그 |
| postgres / redis | Docker | 5432 / 6379 | 저장/캐시 |
| ollama (LLM) | **호스트 네이티브** | 11434 | gemma3:4b |
| GPT-SoVITS api_v2 | **호스트 네이티브** | 9880 | 선택(고품질 TTS) |

호스트 provider는 컨테이너에서 `host.docker.internal`로 접근한다.

---

## 1. 사전 준비 (최초 1회)

1. **Docker Desktop** 실행.
2. **`.env` 준비**: 없으면 `cp .env.example .env`. 핵심 값 확인:
   - `LLM_PROVIDER=ollama`, `LLM_MODEL=gemma3:4b`
   - `TTS_PROVIDER=local_espeak` (또는 `gpt_sovits`)
   - 전화용: `TELEPHONY_PORT=8300`, `LANGUAGE=ko-KR`
   - `.env`는 절대 git에 커밋하지 않는다(이미 gitignore).
3. **ollama**(호스트): `ollama serve` 실행 + `ollama pull gemma3:4b`.
4. (선택) **GPT-SoVITS**(호스트, 고품질 TTS): `scripts/gpt_sovits_server.sh` 실행. 설치는
   `docs/06_provider_strategy.md`/`CLAUDE.md` 참조. 미실행 시 espeak로 자동 fallback.

---

## 2. 스택 기동

```bash
# 핵심 서비스 (orchestrator + stt + tts + discord-bot + postgres + redis)
scripts/services.sh on core

# 전화 채널 (ai-orchestrator + telephony-gateway)
scripts/services.sh on telephony

# 대시보드
scripts/services.sh on dashboard

# 상태/헬스 확인
scripts/services.sh status
curl http://localhost:8000/health   # orchestrator
curl http://localhost:8300/health   # telephony-gateway
curl http://localhost:8000/runtime/providers
```

---

## 3. 채널 A — Discord 하이브리드 음성 설문 (DAVE 우회, 오늘 동작)

> Discord는 2026-03-02부터 DAVE(E2E 음성 암호화)를 강제해 **음성 수신이 차단**됐다.
> 그래서 **질문은 음성으로 들려주고(SEND), 답변은 텍스트로 받는** 하이브리드를 기본으로 한다.

1. 사용자가 봇이 있는 **음성 채널에 입장**.
2. 텍스트 채널에 `!survey voice-start` → 봇이 q1을 **음성으로 재생** + "텍스트로 답하세요" 안내.
3. `!survey answer 만족합니다` → 봇이 q2를 음성으로 재생. 반복.
4. 마지막 답변 후 **완료 메시지**.

- 질문 음색을 GPT-SoVITS로: `.env`의 `TTS_PROVIDER=gpt_sovits`로 두고 GPT-SoVITS 서버 실행
  → 재생성 `scripts/services.sh rebuild tts-service ai-orchestrator`.
- `VOICE_ANSWER_MODE=audio`는 레거시 마이크 캡처(현재 DAVE로 단편만 잡혀 실사용 불가).

---

## 4. 채널 B — 전화(Twilio) 음성 설문 ★실 스모크 절차

전화로 걸면 봇이 한국어로 질문하고, 발신자가 **음성으로 답하면 Twilio가 STT**해 transcript를
게이트웨이로 보내고, orchestrator(ollama)가 분석·저장한다. (Option A)

### 4.1 게이트웨이 + 공개 터널 준비 (운영자 측)

```bash
# 1) 전화 채널 기동
scripts/services.sh on telephony
curl http://localhost:8300/health     # {"status":"ok",...}

# 2) 공개 HTTPS 터널 (Twilio가 게이트웨이에 도달하도록)
#    cloudflared 퀵 터널은 계정 없이 임시 공개 URL을 준다.
brew install cloudflared               # 최초 1회
cloudflared tunnel --url http://localhost:8300
#    → 출력의 https://<무작위>.trycloudflare.com 를 복사 (이것이 PUBLIC URL)

# 3) 공개 URL이 게이트웨이에 닿는지 확인
curl https://<무작위>.trycloudflare.com/health
```

> ngrok을 쓰면 `ngrok http 8300`도 동일하게 동작(계정/authtoken 필요).
> 터널 URL은 **임시**다 — 터널 프로세스를 끄거나 재시작하면 URL이 바뀐다. 바뀌면 Twilio 웹훅도 갱신.

### 4.2 Twilio 번호 웹훅 설정 (Twilio Console)

1. [Twilio Console](https://console.twilio.com) 로그인. (무료 체험 계정도 가능 —
   단, 체험 계정은 **검증된 전화번호로만** 발신/수신 가능.)
2. **Phone Numbers → Manage → Active numbers → (Voice 가능한 번호 선택)**.
   번호가 없으면 **Buy a number**로 Voice 지원 번호 구매(체험 크레딧 사용 가능).
3. 번호 상세의 **Voice Configuration**:
   - **A call comes in** → **Webhook**
   - URL: `https://<무작위>.trycloudflare.com/voice/incoming`
   - HTTP method: **HTTP POST**
4. **Save configuration**.

`<Gather>`의 `action`은 상대경로(`/voice/answer`)라 같은 터널 도메인으로 자동 해석된다 —
incoming URL만 맞추면 된다.

### 4.3 통화 (발신자 측)

1. 설정한 Twilio 번호로 **전화를 건다**.
2. "현재 캠퍼스 시설에 얼마나 만족하시나요?" 가 들리면 **한국어로 또박또박 답한다**
   (예: "매우 만족합니다").
3. 다음 질문에 차례로 답한다(자유응답 포함).
4. 마지막에 "응답해 주셔서 감사합니다. 설문이 완료되었습니다." 후 통화 종료.

### 4.4 결과 확인 (운영자 측)

```bash
# 게이트웨이 로그(요청 흐름)
scripts/services.sh logs telephony-gateway

# 감사 로그: channel=phone, actor=hash:... (발신번호 원본 미저장)
curl "http://localhost:8000/audit/events?limit=10"

# 대시보드: 의견 종합 / 중요 로그
open http://localhost:8501/insights
open http://localhost:8501/logs
```

### 4.5 (선택) 전화에서 GPT-SoVITS 음색으로 질문 재생

기본은 Twilio의 `<Say ko-KR>`(클라우드 TTS)다. orchestrator가 만든 GPT-SoVITS/espeak wav를
전화로 들려주려면:

```bash
# .env
TELEPHONY_USE_TTS_AUDIO=true
PUBLIC_BASE_URL=https://<무작위>.trycloudflare.com   # 터널 URL과 동일
```
재생성 후 통화하면 `<Play>{PUBLIC_BASE_URL}/media/{wav}>`로 우리 합성 음성을 재생한다.
(터널이 게이트웨이 8300으로 가므로 `/media/`도 같은 URL로 서빙된다.)

---

## 5. 전화 없이 로컬 검증 (스모크 리허설)

Twilio/전화 없이 게이트웨이 흐름 전체를 확인:

```bash
scripts/telephony_sim.sh
# 또는 답변을 직접 지정
scripts/telephony_sim.sh http://localhost:8300 +821012345678 "매우 만족" "주차 공간" "전반적으로 좋습니다"
```
각 단계 TwiML을 출력하며 `<Hangup/>`까지 완주하면 정상.

---

## 6. 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| 전화 시 "application error" 안내음 | 게이트웨이/터널 다운 → `curl <PUBLIC>/health` 확인, `scripts/services.sh status` |
| Twilio가 웹훅 11200/502 | 터널 URL 오타 또는 만료 → 새 `cloudflared` URL로 웹훅 갱신 |
| 질문이 반복됨(다음으로 안 넘어감) | 답이 옵션에 매칭 안 됨(single_choice) → 또렷이 보기 그대로 답하거나, ollama(gemma3:4b) 응답 품질 점검. (free_text는 재질문 안 함) |
| 한국어 인식 부정확 | Twilio `language=ko-KR` 협대역(8kHz) 한계 → 또박또박, 조용한 환경. 로컬 whisper로 옮기려면 Option B(11b) 필요 |
| 체험 계정에서 통화 안 됨 | Twilio 체험은 **검증된 번호만** → 발신 번호를 Verified Caller IDs에 등록 |
| 터널 URL이 매번 바뀜 | 퀵 터널 특성. 고정하려면 Cloudflare 계정 named tunnel 또는 ngrok 고정 도메인 |

---

## 7. 프라이버시 / 비용 주의

- **발신번호**는 `phone:{sha256 12자}`로 해시 저장(원본 미저장). transcript 저장은 `SAVE_TRANSCRIPT`,
  보존기간은 `RAW_AUDIO_RETENTION_DAYS` 등으로 제어. `POST /retention/audio/cleanup`로 정리.
- **Option A는 오디오가 Twilio 클라우드를 경유**(STT를 Twilio가 수행)한다 → 완전 로컬이 필요하면
  Option B(Twilio Media Streams + 로컬 whisper, 11b) 또는 C(자체 SIP, 11c). `docs/08` 참조,
  `rules/guardrails.md`에 명시.
- **비용**: Twilio는 통화 분당 + speech recognition 과금. 체험 크레딧으로 스모크 가능.

---

## 8. 종료 / 정리

```bash
# 터널 종료: cloudflared 프로세스 Ctrl+C
# 서비스 중지
scripts/services.sh off telephony
scripts/services.sh off dashboard
# 전체 내리기(볼륨 유지)
docker compose --profile dashboard --profile devtools --profile telephony down
```

---

## 부록 A — 빠른 명령 요약

```bash
scripts/services.sh on core                 # 핵심 서비스
scripts/services.sh on telephony            # 전화 게이트웨이
cloudflared tunnel --url http://localhost:8300   # 공개 URL
# Twilio 번호 Voice 웹훅 → https://<tunnel>/voice/incoming (POST)
scripts/telephony_sim.sh                    # 전화 없이 리허설
curl "http://localhost:8000/audit/events?limit=10"   # 결과 확인
```
