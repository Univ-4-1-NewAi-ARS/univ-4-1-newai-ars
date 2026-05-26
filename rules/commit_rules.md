# Commit Rules

## Commit Message Format

```text
phase {번호}: {작업 요약}
- Added:
- Changed:
- Tested:
- Docs:
- Report:
```

## Pre-Commit Checklist

1. `.env`가 stage되어 있지 않은지 확인한다.
2. `.env.example`에는 placeholder만 있는지 확인한다.
3. 테스트를 실행한다.
4. `log-report/`에 phase 보고서를 작성한다.
5. `log-done/`에 완료 기록을 작성한다.
6. API 또는 data model 변경 시 관련 docs를 갱신한다.
7. `git status`를 확인한다.
