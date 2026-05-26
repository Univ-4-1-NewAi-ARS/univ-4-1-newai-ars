# Coding Convention

## Python

- Python 3.11 이상을 기준으로 한다.
- FastAPI, Pydantic v2, SQLAlchemy 또는 SQLModel, httpx, pytest를 우선 사용한다.
- provider interface와 router를 먼저 두고 implementation을 분리한다.
- 모델명, URL, API key, port는 코드에 하드코딩하지 않는다.
- 설정은 pydantic-settings 또는 python-dotenv로 로드한다.

## Structure

- service별 코드는 `services/{service-name}` 아래에 둔다.
- shared contract가 필요해지면 phase 문서에 먼저 기록하고 최소 범위로 도입한다.
- mock provider는 외부 네트워크 없이 테스트 가능해야 한다.

## Comments and Logging

- 자명한 주석은 쓰지 않는다.
- fallback, retry, privacy mask 같은 정책 지점은 짧게 설명한다.
- 로그에는 token, API key, raw Discord user id, 민감 transcript를 직접 남기지 않는다.
