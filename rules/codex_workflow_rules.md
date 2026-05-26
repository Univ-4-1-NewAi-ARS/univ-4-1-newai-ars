# Codex Workflow Rules

## 작업 전 문서 읽기 규칙

- 작업 시작 전 현재 phase와 관련된 `docs/`, `rules/`, `log-report/`, `log-done/` 파일을 확인한다.
- DB schema 변경 전 `docs/04_data_model.md`와 `infra/postgres/init/`를 확인한다.
- API 변경 전 `docs/03_api_spec.md`를 확인한다.
- Provider 변경 전 `docs/06_provider_strategy.md`를 확인한다.

## Phase 단위 작업 규칙

- 가장 앞선 미완료 phase부터 진행한다.
- 한 phase에서 다음 phase의 과도한 구현을 포함하지 않는다.
- 각 phase는 기획/문서, 구현, 테스트, 검증 보고서, 완료 기록, commit을 포함한다.

## 테스트 후 보고 규칙

- 실행한 테스트 명령과 결과를 `log-report/`에 기록한다.
- 테스트를 실행하지 못한 경우 이유와 후속 조치를 명확히 쓴다.
- known issue는 숨기지 않고 다음 action과 함께 남긴다.

## `log-report` / `log-done` 기록 규칙

- phase 종료 시 `log-report/YYYY-MM-DD_phase-{번호}_{짧은제목}.md`를 작성한다.
- 단위 작업 종료 시 `log-done/YYYY-MM-DD_done_{작업요약}.md`를 작성한다.
- 보고서에는 goal, implemented, changed files, test result, validation, known issues, next actions, commit message를 포함한다.

## Commit 규칙

- `.env`가 stage되지 않았는지 확인한다.
- `.env.example`은 commit 가능하다.
- 테스트와 보고서 작성 후 commit한다.
- commit message는 phase 번호, added/changed/tested/docs/report 항목을 포함한다.
