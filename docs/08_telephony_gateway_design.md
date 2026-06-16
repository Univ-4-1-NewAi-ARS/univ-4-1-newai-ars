# Telephony Gateway Design (DAVE Bypass)

> **상태: 11a 구현 완료 (2026-06-16)** — `services/telephony-gateway` (FastAPI, :8300)가
> Option A(Twilio Programmable Voice + `<Gather input="speech">`) 루프를 구현했다.
> orchestrator `SurveyChannel`에 `"phone"` 추가, transcript 경로 재사용, `<Say>` 기본 +
> `<Play>` 옵션, `phone:{hash}` 발신번호 정규화. pytest 8 passed.
> `scripts/telephony_sim.sh`로 Twilio 없이 로컬에서 전체 전화 흐름을 검증한다(엔드투엔드 PASS).
> 11b(Media Streams + 로컬 whisper), 11c(SIP)는 미구현.

## 배경 / 동기

Discord 음성 **수신**은 2026-03-02부터 강제된 DAVE(종단간 음성 암호화)로 인해
현재 어떤 Python Discord 라이브러리도 복호화하지 못해 사실상 차단되었다
(`discord.opus.OpusError: corrupted stream` → 단편만 캡처). 이는 우리 코드/버전
문제가 아니라 플랫폼 레벨 변경이다. 따라서 **원래 로드맵의 최종 목표였던 실제 전화망
채널로 전환**해 Discord를 우회한다.

핵심 자산: **AI Orchestrator는 이미 채널 비종속적**이다. `POST /sessions`,
`POST /sessions/{id}/answers`(transcript 또는 audio_path), `GET /sessions/{id}/summary`만
사용하므로, Discord bot을 전화망 게이트웨이로 **교체**하기만 하면 STT/LLM/TTS/통계/대시보드
전 파이프라인을 그대로 재사용한다.

## 설계 원칙

1. **Orchestrator 무변경(거의)**: 동일한 sessions/answers API 사용. 유일한 변경은
   `SurveyChannel` literal에 `"phone"` 추가(하위 호환).
2. **채널 어댑터만 교체**: `discord-bot`의 `_voice_survey_loop`(TTS 재생 → 캡처 →
   STT → 제출 → 다음 질문)를 전화 미디어 경로 위에서 그대로 미러링.
3. **Provider 전략 재사용**: local_whisper STT, local_espeak/gpt_sovits TTS,
   no-speech 무결성, retention/privacy 모두 그대로 적용.
4. **무결성/프라이버시 유지**: 발신번호는 `phone:{hash}`로 정규화. 클라우드 경유 여부를
   guardrails에 명시.

## 타깃 아키텍처

```
PSTN 발신자 ──▶ [전화망 제공자] ──▶ telephony-gateway (신규 FastAPI 서비스)
                                        │  CallSid 기준 per-call 설문 루프
                                        │  발신자 오디오 → 16k mono wav
                                        │  TTS wav → 발신자 재생
                                        ▼
                                  ai-orchestrator (:8000)  ← 변경 없음
                                  STT / LLM / TTS / stats / dashboard 재사용
```

## 스택 옵션 (핵심 의사결정)

### Option A — Twilio Programmable Voice + `<Gather input="speech">` (최속 검증)
- 인바운드 번호 → 웹훅(TwiML). `<Play>`로 질문 음성 재생 → `<Gather input="speech"
  language="ko-KR" action=...>` → **Twilio가 STT 수행** → transcript를 게이트웨이로
  POST → orchestrator에 transcript 제출 → 다음 질문 TwiML 반환.
- 장점: 미디어/RTP 처리 불필요, 수 시간 내 실 PSTN 동작, 코드 최소.
- 단점: STT가 Twilio 클라우드(로컬 whisper 미사용), 오디오 외부 유출(프라이버시),
  분당 과금, 공개 HTTPS 웹훅 필요(ngrok/터널/클라우드).

### Option B — Twilio Media Streams + 로컬 whisper (로컬 STT 유지) ★권장 타깃
- `<Connect><Stream>`로 WebSocket 개설 → Twilio가 8kHz μ-law 오디오 스트리밍 →
  게이트웨이가 발화 단위(무음/VAD) 버퍼링 → μ-law→PCM16, 8k→16k 리샘플 →
  orchestrator에 audio_path 제출(whisper) → TTS wav를 `<Play>`로 재생.
- 장점: **STT 로컬 유지(whisper)**, 기존 provider 전략·no-speech 무결성 재사용.
- 단점: WS 미디어/μ-law 디코드/바지인(barge-in) 처리 복잡, 여전히 클라우드 전송 + 공개 엔드포인트.

### Option C — 자체 호스팅 SIP(Asterisk/FreeSWITCH + AudioSocket) (완전 로컬/사설)
- SIP PBX가 호 수신(PSTN은 SIP 트렁크, 테스트는 SIP 소프트폰) → dialplan이
  AudioSocket/ARI로 raw PCM을 게이트웨이에 TCP 스트리밍 → whisper → orchestrator →
  TTS wav 재생.
- 장점: **완전 로컬·사설**(guardrails 부합), 분당 STT 비용 없음.
- 단점: 인프라 최중량(Asterisk 설정, RTP/코덱, SIP 트렁크), 셋업 최장.

## 권장 경로

프라이버시 가드레일이 프로젝트 핵심 가치이고 이미 로컬 whisper/espeak/gpt_sovits에
투자했으므로 전략적 타깃은 **Option B**(전화 도달은 Twilio, STT/TTS는 로컬)다.
- **11a**: Option A로 엔드투엔드 ARS 루프를 실 전화로 최단 검증(디딤돌).
- **11b**: Option B로 로컬 whisper STT 복원(프라이버시 + 재사용).
- **11c**: Option C로 무클라우드 자체 호스팅 엔드게임.

## 신규 서비스: `telephony-gateway`

FastAPI 서비스. 엔드포인트(A/B 공용):
- `POST /voice/incoming` — 인바운드 호 TwiML: 세션 시작 → q1 재생 → gather/stream.
- `POST /voice/answer` — Gather 결과(transcript) 또는 스트림 종료 → 답변 제출 → 다음 TwiML.
- `GET /media/tts/{file}.wav` — orchestrator TTS wav를 `<Play>`용으로 서빙.
- (Option B) `WS /voice/stream` — Twilio Media Streams 수신.

구현 메모:
- `OrchestratorClient` 패턴 재사용(start_session / submit_answer / submit_audio_answer /
  get_summary). discord-bot의 클라이언트를 거의 그대로 이식.
- per-call 상태를 Twilio `CallSid`로 키잉(discord의 conversation_key 대응).
- 발화 단위 캡처: Option A는 Twilio가 처리, Option B는 게이트웨이가 무음 기반 종료
  (discord의 `_capture_until_silence` 로직 이식).

## Orchestrator 접점 (최소 변경)

- `models.py`의 `SurveyChannel`에 `"phone"` 추가(하위 호환).
- Option A(transcript 경로): orchestrator STT 불필요(transcript 직접 제출) — 기존 경로 그대로.
- Option B(audio 경로): 게이트웨이가 wav를 공유 `/data/audio`에 쓰고 audio_path 제출 —
  기존 STT 경로 그대로(이번에 추가한 no-speech 무결성 포함).

## 오디오 포맷 매핑

- 전화 미디어: 8kHz μ-law mono(PCMU). 게이트웨이: μ-law→PCM16 → 8k→16k 리샘플 → mono.
  (stdlib `audioop` 또는 numpy; `VoiceRecorder._to_mono_16k` 다운믹스 패턴 재사용.)
- TTS 재생: espeak/gpt_sovits는 16k/22k wav 생성 → Twilio `<Play>`는 HTTPS wav/mp3 허용 →
  필요 시 8k로 리샘플 후 서빙.

## 프라이버시 / 가드레일

- Option A/B는 오디오가 Twilio 클라우드 경유 → `rules/guardrails.md`에 명시 필요.
  Option C는 오디오 완전 로컬.
- `participant_ref`: 발신번호(E.164)를 `phone:{12-char-digest}`로 해시(현 discord 해시와 동일 패턴).
- `SAVE_RAW_AUDIO` / 보존기간 / transcript redaction 그대로 적용.

## 테스트 전략

- 단위: TwiML 생성, transcript 제출 흐름, μ-law 디코드 round-trip(`VoiceRecorder` 테스트 패턴),
  orchestrator HTTP는 `httpx.MockTransport`로 목킹.
- 로컬 스모크: Twilio 시험 크리덴셜 + 터널(ngrok) 또는 Option C의 SIP 소프트폰.
- orchestrator 경로(text/audio)는 이미 검증됨.

## 리스크 / 미해결 질문

- **공개 엔드포인트**: Twilio 웹훅엔 공개 HTTPS 필요(ngrok/클라우드 런).
- **협대역 한국어 STT**: 8kHz 전화 오디오는 whisper 정확도 하락 가능 → 전화 튜닝/모델 크기 검토.
- **턴테이킹/바지인**: 발신자가 TTS 위로 말할 때 처리.
- **비용**: Twilio 분당 + STT(Option A).
- **번호 확보**: PSTN 인바운드 번호(Twilio 구매 또는 SIP 트렁크).

## 다음 단계(11a PoC 범위)

1. `SurveyChannel`에 `"phone"` 추가.
2. `telephony-gateway` 스켈레톤(FastAPI) + `OrchestratorClient` 이식.
3. Option A TwiML 루프(incoming → play q1 → gather → answer → next/완료).
4. 단위 테스트(TwiML/transcript 제출, 목 orchestrator).
5. 터널 + Twilio 시험 번호로 1콜 엔드투엔드 스모크.
