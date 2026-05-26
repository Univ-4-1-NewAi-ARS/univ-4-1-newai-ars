import httpx
from fastapi.testclient import TestClient

from app.main import DashboardClient, Settings, create_app


def test_dashboard_health() -> None:
    app = create_app(Settings(orchestrator_base_url="http://orchestrator"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "dashboard"


def test_dashboard_renders_stats() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
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

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport, base_url="http://orchestrator")
    dashboard_client = DashboardClient("http://orchestrator", client=async_client)
    app = create_app(Settings(orchestrator_base_url="http://orchestrator"), dashboard_client=dashboard_client)

    with TestClient(app) as client:
        response = client.get("/surveys/campus_opinion_survey")

    assert response.status_code == 200
    assert "campus_opinion_survey" in response.text
    assert "Responses" in response.text
