import httpx
from fastapi.testclient import TestClient

from app.main import DashboardClient, Settings, create_app


SETTINGS = Settings(
    orchestrator_base_url="http://orchestrator",
    stt_base_url="http://stt",
    tts_base_url="http://tts",
)


def _mock_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/insights"):
        return httpx.Response(
            200,
            json={
                "survey_id": "campus_opinion_survey",
                "response_count": 3,
                "sentiment_counts": {"positive": 2, "negative": 1},
                "keyword_counts": {"주차 공간": 2, "도서관": 1},
                "questions": [
                    {
                        "question_id": "q1",
                        "text": "현재 캠퍼스 시설에 얼마나 만족하시나요?",
                        "answer_type": "single_choice",
                        "response_count": 2,
                        "sentiment_counts": {"positive": 2},
                        "option_counts": {"만족": 2},
                        "keyword_counts": {},
                        "opinions": [],
                    },
                    {
                        "question_id": "q2",
                        "text": "가장 개선이 필요한 영역은?",
                        "answer_type": "free_text",
                        "response_count": 1,
                        "sentiment_counts": {"negative": 1},
                        "option_counts": {},
                        "keyword_counts": {"주차 공간": 1},
                        "opinions": [
                            {
                                "text": "주차 공간이 부족해서 개선이 필요합니다",
                                "sentiment": "negative",
                                "keywords": ["주차 공간", "부족"],
                                "confidence": 0.8,
                            }
                        ],
                    },
                ],
                "generated_at": "2026-06-16T00:00:00Z",
            },
        )
    if path.endswith("/stats"):
        return httpx.Response(
            200,
            json={
                "survey_id": "campus_opinion_survey",
                "session_count": 2,
                "response_count": 3,
                "option_counts": {"q1": {"2": 2}},
                "sentiment_counts": {"positive": 2, "neutral": 1},
                "generated_at": "2026-05-27T00:00:00Z",
            },
        )
    if path == "/runtime/providers":
        return httpx.Response(
            200,
            json={
                "llm": {"provider": "ollama", "status": "configured", "model": "gemma3:4b"},
                "stt": {"provider": "local_whisper", "status": "configured"},
                "tts": {"provider": "local_espeak", "status": "configured"},
            },
        )
    if path == "/audit/events":
        return httpx.Response(
            200,
            json={
                "count": 1,
                "events": [
                    {
                        "id": "abc",
                        "event_type": "session_started",
                        "severity": "info",
                        "session_id": "deadbeef-0000",
                        "actor_ref": "discord:hash",
                        "details": {"survey_id": "campus_opinion_survey", "channel": "discord_voice"},
                        "created_at": "2026-06-16T00:00:00Z",
                    }
                ],
            },
        )
    if path == "/health":
        return httpx.Response(200, json={"status": "ok", "service": request.url.host, "provider": "local"})
    return httpx.Response(404, json={"detail": "not found"})


def _build_client() -> TestClient:
    transport = httpx.MockTransport(_mock_handler)
    async_client = httpx.AsyncClient(transport=transport)
    dashboard_client = DashboardClient(SETTINGS, client=async_client)
    app = create_app(SETTINGS, dashboard_client=dashboard_client)
    return TestClient(app)


def test_dashboard_health() -> None:
    app = create_app(SETTINGS)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "dashboard"


def test_summary_renders_stats() -> None:
    with _build_client() as client:
        response = client.get("/surveys/campus_opinion_survey")
    assert response.status_code == 200
    assert "campus_opinion_survey" in response.text
    assert "Responses" in response.text
    assert "Sentiment" in response.text


def test_services_page_shows_health_and_providers() -> None:
    with _build_client() as client:
        response = client.get("/services")
    assert response.status_code == 200
    assert "서비스 헬스" in response.text
    assert "AI Orchestrator" in response.text
    assert "ollama" in response.text  # provider runtime panel
    assert "정상" in response.text


def test_logs_page_renders_audit_events() -> None:
    with _build_client() as client:
        response = client.get("/logs")
    assert response.status_code == 200
    assert "중요 로그" in response.text
    assert "session_started" in response.text


def test_insights_page_synthesizes_opinions() -> None:
    with _build_client() as client:
        response = client.get("/insights")
    assert response.status_code == 200
    assert "의견 종합" in response.text
    assert "핵심 키워드" in response.text
    assert "주차 공간" in response.text  # keyword theme
    assert "주차 공간이 부족해서 개선이 필요합니다" in response.text  # free-text opinion
    assert "만족" in response.text  # single-choice option label


def test_nav_present_on_every_page() -> None:
    with _build_client() as client:
        for path in ("/", "/insights", "/services", "/logs"):
            response = client.get(path)
            assert response.status_code == 200
            assert "의견 종합" in response.text
            assert "서비스 헬스" in response.text
