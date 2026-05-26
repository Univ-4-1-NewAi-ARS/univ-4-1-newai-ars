# Provider Strategy

## 공통 원칙

Provider는 interface, router, implementation으로 분리한다. 선택은 `.env`에서 이뤄지며 코드 수정 없이 교체 가능해야 한다. Phase 초기에는 mock provider가 기본값이다.

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

## `.env` 기반 교체 방식

예시:

```dotenv
LLM_PROVIDER=ollama
LLM_BASE_URL=http://host.docker.internal:11434
LLM_MODEL=qwen2.5:7b-instruct
STT_PROVIDER=mock
TTS_PROVIDER=cached_file
```

Provider router는 알 수 없는 provider 값이면 error를 명확히 기록하고, phase 설정에 따라 mock 또는 graceful skip을 선택한다.

## Local/API Fallback 정책

- local provider를 우선 실행한다.
- timeout, connection error, schema validation 실패를 구분해 로그에 남긴다.
- fallback 사용 시 `agent_logs.fallback_used=true`로 기록한다.
- API fallback은 `.env`에서 명시적으로 허용한 경우만 사용한다.
- API key가 placeholder이거나 누락된 경우 fallback을 건너뛰고 known issue로 기록한다.
