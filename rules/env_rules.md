# Environment Rules

## General

- 모든 runtime 설정은 `.env`에서 온다.
- `.env.example`은 새 환경 변수를 추가할 때 함께 갱신한다.
- 실제 secret은 문서, 코드, commit message에 기록하지 않는다.

## Provider Settings

- `LLM_PROVIDER`, `STT_PROVIDER`, `TTS_PROVIDER`는 router 선택에 사용한다.
- provider unknown 상태는 명확한 오류 또는 mock fallback으로 처리한다.
- host native Ollama/LM Studio는 `host.docker.internal`로 접근한다.
- 모델 자산(`models/`)은 commit하지 않는다. Whisper는 첫 실행 시 자동 다운로드되고, Piper voice는 `scripts/provision_piper.sh`로 provision한다.
- `PIPER_MODEL_PATH`는 provision한 `.onnx` 경로와 일치해야 하며, 모델 부재 시 TTS fallback chain이 사용된다.

## Storage Settings

- `SAVE_RAW_AUDIO`와 `SAVE_TRANSCRIPT`는 저장 정책의 최상위 스위치다.
- 보관 기간은 retention env로 제어한다.
- DB password는 로컬 `.env`에서만 실제값을 사용한다.
