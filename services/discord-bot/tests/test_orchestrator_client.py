import httpx
import pytest

from app.orchestrator_client import OrchestratorClient


@pytest.mark.asyncio
async def test_orchestrator_client_start_session() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sessions"
        return httpx.Response(
            201,
            json={
                "session_id": "session-1",
                "survey_id": "campus_opinion_survey",
                "status": "in_progress",
                "current_question": {
                    "question_id": "q1",
                    "text": "질문",
                    "answer_type": "single_choice",
                    "options": [],
                },
                "tts": None,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ai-orchestrator:8000") as client:
        payload = await OrchestratorClient("http://ai-orchestrator:8000", client=client).start_session(
            survey_id="campus_opinion_survey",
            participant_ref="discord:masked",
        )

    assert payload["session_id"] == "session-1"
