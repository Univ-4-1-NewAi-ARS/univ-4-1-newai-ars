# Provider Strategy

## 공통 원칙

Provider는 interface, router, implementation으로 분리한다. 선택은 `.env`에서 이뤄지며 코드 수정 없이 교체 가능해야 한다. Phase 8부터 local real provider를 우선 사용하고, 운영 안정성을 위해 mock/cached fallback은 명시 env가 허용할 때 유지한다.

## LLM Provider 전략

지원 후보:

- `mock`: deterministic test response
- `ollama`: macOS host native Ollama
- `lmstudio`: OpenAI-compatible local endpoint
- `openai`: API fallback

환경 변수:

- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_TIMEOUT_SEC`
- `LLM_USE_API_FALLBACK`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

LLM 응답은 Pydantic schema로 검증한다. JSON parsing 실패 시 retry를 수행하고, `LLM_USE_API_FALLBACK=true`이면 fallback provider를 시도한다.

Phase 2 구현 상태:

- `LLMRouter`가 `LLM_PROVIDER=mock|ollama|lmstudio|openai`를 해석한다.
- `AnswerAnalyzer`가 provider 응답을 `AgentResult` Pydantic 모델로 검증한다.
- `LLM_PARSE_RETRY_COUNT` 횟수만큼 JSON parse/schema validation retry를 수행한다.
- Ollama, LM Studio, OpenAI provider skeleton이 있으며 설정 누락 또는 connection failure 시 `ProviderUnavailable`로 graceful skip된다.
- local provider 실패 후 API fallback이 불가능하면 mock provider로 최종 fallback하여 Phase 1 text flow가 중단되지 않게 한다.
- fallback 사용 여부와 retry count는 `agent_logs`에 저장된다.

Phase 8 구현 상태:

- local Ollama primary path를 runtime 검증했다.
- 현재 검증 모델은 host Ollama의 `gemma3:4b`다.
- `LLM_USE_MOCK_FALLBACK=true`이면 Ollama/API 실패 후 mock으로 복구한다.
- `LLM_USE_MOCK_FALLBACK=false`이면 mock fallback을 사용하지 않고 provider failure를 노출한다.
- 실사용 prompt는 compact JSON field contract를 사용해 4B급 local model timeout 위험을 줄인다.

## STT Provider 전략

지원 후보:

- `mock`: transcript fixture 반환
- `local_whisper`: local Whisper adapter
- `openai`: API fallback
- `deepgram`: API fallback 후보

환경 변수:

- `STT_PROVIDER`
- `STT_BASE_URL`
- `STT_MODEL`
- `STT_LANGUAGE`
- `STT_USE_API_FALLBACK`

초기 phase에서는 audio file path 또는 mock transcript를 우선한다. streaming STT는 Discord Voice MVP 이후 검토한다.

Phase 3 구현 상태:

- `stt-service` FastAPI 앱이 `/health`, `/transcribe`를 제공한다.
- `mock` provider는 audio path 기반 deterministic transcript를 반환한다.
- `file` provider는 `/data/transcripts/{audio_stem}.txt` 파일을 transcript source로 사용할 수 있다.
- Orchestrator는 `ServiceSTTProvider` HTTP adapter로 STT service를 호출할 수 있다.

Phase 8 구현 상태:

- `local_whisper` provider를 `faster-whisper` 기반으로 구현했다.
- `STT_DEVICE=cpu`, `STT_COMPUTE_TYPE=int8`, `STT_MODEL_DIR=/models/whisper`를 지원한다.
- `local_whisper` 실패 시 file fixture를 먼저 확인하고, `STT_USE_MOCK_FALLBACK=true`이면 mock으로 복구한다.
- runtime smoke에서 generated wav를 `/data/audio`로 넣어 `local_whisper` provider가 fallback 없이 transcript를 반환함을 확인했다.

## TTS Provider 전략

지원 후보:

- `mock`: fixed audio path 반환
- `cached_file`: 미리 준비된 wav/mp3 재사용
- `local_piper`: local Piper adapter
- `openai`: API fallback

환경 변수:

- `TTS_PROVIDER`
- `TTS_BASE_URL`
- `TTS_VOICE`
- `TTS_LANGUAGE`
- `TTS_USE_API_FALLBACK`

캐시 키는 survey id, question id, voice, language를 포함한다.

Phase 3 구현 상태:

- `tts-service` FastAPI 앱이 `/health`, `/synthesize`를 제공한다.
- `cached_file` provider는 deterministic wav path를 반환하고 파일이 없으면 silent wav placeholder를 생성한다.
- Orchestrator는 `ServiceTTSProvider` HTTP adapter로 TTS service를 호출할 수 있다.

Phase 8 구현 상태:

- `local_espeak` provider를 Docker-local real TTS path로 구현했다.
- `local_piper` provider는 `PIPER_BIN`과 `PIPER_MODEL_PATH`가 있을 때 사용한다.
- `TTS_FALLBACK_PROVIDER=cached_file`와 `TTS_USE_CACHED_FALLBACK=true`로 TTS failure 시 cached wav fallback을 유지한다.
- runtime smoke에서 `local_espeak`가 provider-specific wav를 생성하고 `fallback_used=false`를 반환함을 확인했다.

Phase 9 구현 상태 (수정):

- `piper-tts` pip 패키지는 `espeak`, `text`, `pinyin` phoneme type만 지원한다. 커뮤니티 KSS 한국어 모델(`neurlang/piper-onnx-kss-korean`)은 `pygoruut` phoneme type을 사용해 pip piper-tts와 구조적으로 호환되지 않는다.
- `piper-tts` 패키지 dependency를 제거했다. `local_piper` subprocess 경로는 코드에 유지되며, 향후 `espeak` phoneme type의 한국어 모델 또는 컴파일된 piper 바이너리 사용 시 활용 가능하다.
- `scripts/provision_piper.sh`가 모델 config의 `phoneme_type`을 읽어 pip piper-tts와 호환되지 않는 경우 경고를 출력하도록 개선했다.
- 현재 한국어 TTS working path: `TTS_PROVIDER=local_espeak`(`.env.example` 기본값). espeak-ng는 한국어를 지원하며 Phase 8에서 runtime 검증 완료.
- `local_piper` 합성 실패 시 기존 fallback chain(`tts_fallback_provider` → `cached_file`)은 유지된다.

## `.env` 기반 교체 방식

예시:

```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://host.docker.internal:11434
LLM_MODEL=gemma3:4b
LLM_USE_MOCK_FALLBACK=true
STT_PROVIDER=local_whisper
STT_USE_MOCK_FALLBACK=true
TTS_PROVIDER=local_espeak
TTS_FALLBACK_PROVIDER=cached_file
TTS_USE_CACHED_FALLBACK=true
```

Provider router는 알 수 없는 provider 값이면 error를 명확히 기록하고, phase 설정에 따라 mock 또는 graceful skip을 선택한다.

## Local/API Fallback 정책

- local provider를 우선 실행한다.
- timeout, connection error, schema validation 실패를 구분해 로그에 남긴다.
- fallback 사용 시 `agent_logs.fallback_used=true`로 기록한다.
- API fallback은 `.env`에서 명시적으로 허용한 경우만 사용한다.
- API key가 placeholder이거나 누락된 경우 fallback을 건너뛰고 known issue로 기록한다.
- Phase 8 기본 운영은 real provider 우선, 명시 fallback 허용이다. local model/provider가 느리거나 실패해도 survey loop가 중단되지 않도록 mock/cached fallback을 유지한다.
