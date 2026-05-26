import httpx
import pytest

from app.orchestrator_client import OrchestratorClient
from app.text_flow import TextSurveyManager


@pytest.mark.asyncio
async def test_text_flow_start_answer_complete() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/sessions":
            return httpx.Response(
                201,
                json={
                    "session_id": "session-1",
                    "survey_id": "campus_opinion_survey",
                    "status": "in_progress",
                    "current_question": {
                        "question_id": "q1",
                        "text": "현재 캠퍼스 시설에 얼마나 만족하시나요?",
                        "answer_type": "single_choice",
                        "options": [{"id": "2", "label": "만족"}],
                    },
                    "tts": None,
                },
            )
        if request.url.path == "/sessions/session-1/answers":
            return httpx.Response(
                200,
                json={
                    "session_id": "session-1",
                    "status": "completed",
                    "agent_result": {
                        "question_id": "q1",
                        "raw_transcript": "만족합니다",
                        "cleaned_text": "만족합니다",
                        "answer_type": "single_choice",
                        "selected_option": "2",
                        "confidence": 0.86,
                        "sentiment": "positive",
                        "keywords": ["만족합니다"],
                        "needs_retry": False,
                        "review_required": False,
                        "reason": "matched",
                    },
                    "next_question": None,
                    "tts": None,
                },
            )
        if request.url.path == "/sessions/session-1/summary":
            return httpx.Response(
                200,
                json={
                    "session_id": "session-1",
                    "survey_id": "campus_opinion_survey",
                    "status": "completed",
                    "current_question_id": None,
                    "response_count": 1,
                    "responses": [],
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ai-orchestrator:8000") as client:
        manager = TextSurveyManager(
            client=OrchestratorClient("http://ai-orchestrator:8000", client=client),
            default_survey_id="campus_opinion_survey",
        )
        question = await manager.start(conversation_key="channel:user", discord_user_id="123")
        completion = await manager.answer(conversation_key="channel:user", transcript="만족합니다")

    assert "q1" in question
    assert "설문이 완료되었습니다" in completion
    assert calls == ["/sessions", "/sessions/session-1/answers", "/sessions/session-1/summary"]
