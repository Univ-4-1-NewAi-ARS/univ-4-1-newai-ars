import httpx
import pytest

from app.orchestrator_client import NoSpeechDetected, OrchestratorClient
from app.voice_flow import VoiceSurveyManager


@pytest.mark.asyncio
async def test_voice_flow_file_based_audio_answer() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/sessions":
            return httpx.Response(
                201,
                json={
                    "session_id": "voice-session-1",
                    "survey_id": "campus_opinion_survey",
                    "status": "in_progress",
                    "current_question": {
                        "question_id": "q1",
                        "text": "현재 캠퍼스 시설에 얼마나 만족하시나요?",
                        "answer_type": "single_choice",
                        "options": [{"id": "2", "label": "만족"}],
                    },
                    "tts": {
                        "audio_path": "/data/tts/campus_opinion_survey-q1-ko_default.wav",
                        "duration_sec": 2.5,
                        "provider": "cached_file",
                        "cached": True,
                    },
                },
            )
        if request.url.path == "/sessions/voice-session-1/answers":
            return httpx.Response(
                200,
                json={
                    "session_id": "voice-session-1",
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
        if request.url.path == "/sessions/voice-session-1/summary":
            return httpx.Response(
                200,
                json={
                    "session_id": "voice-session-1",
                    "survey_id": "campus_opinion_survey",
                    "status": "completed",
                    "current_question_id": None,
                    "response_count": 1,
                    "responses": [],
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ai-orchestrator:8000") as client:
        manager = VoiceSurveyManager(
            client=OrchestratorClient("http://ai-orchestrator:8000", client=client),
            default_survey_id="campus_opinion_survey",
        )
        started = await manager.start(conversation_key="channel:user", discord_user_id="123")
        completed = await manager.submit_audio_file(conversation_key="channel:user", audio_path="/data/audio/q1.wav")

    assert started["audio_path"].endswith("campus_opinion_survey-q1-ko_default.wav")
    assert completed["completed"] is True
    assert "음성 설문이 완료되었습니다" in completed["message"]
    assert calls == ["/sessions", "/sessions/voice-session-1/answers", "/sessions/voice-session-1/summary"]


@pytest.mark.asyncio
async def test_voice_flow_no_speech_returns_signal_not_fabricated_answer() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sessions":
            return httpx.Response(
                201,
                json={
                    "session_id": "voice-session-2",
                    "survey_id": "campus_opinion_survey",
                    "status": "in_progress",
                    "current_question": {"question_id": "q1", "text": "Q1", "answer_type": "single_choice", "options": []},
                    "tts": None,
                },
            )
        if request.url.path == "/sessions/voice-session-2/answers":
            return httpx.Response(422, json={"detail": "No speech detected in audio"})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ai-orchestrator:8000") as client:
        manager = VoiceSurveyManager(
            client=OrchestratorClient("http://ai-orchestrator:8000", client=client),
            default_survey_id="campus_opinion_survey",
        )
        await manager.start(conversation_key="channel:user", discord_user_id="123")
        result = await manager.submit_audio_file(conversation_key="channel:user", audio_path="/data/audio/silence.wav")

    assert result["no_speech"] is True
    assert result["completed"] is False
    # session is preserved so the loop can re-ask the same question
    assert "channel:user" in manager.sessions


def _agent_result(question_id: str) -> dict:
    return {
        "question_id": question_id,
        "raw_transcript": "답변",
        "cleaned_text": "답변",
        "answer_type": "free_text",
        "selected_option": None,
        "confidence": 0.8,
        "sentiment": "neutral",
        "keywords": [],
        "needs_retry": False,
        "review_required": False,
        "reason": "ok",
    }


@pytest.mark.asyncio
async def test_hybrid_text_answer_advances_and_completes() -> None:
    """Spoken question + text answer (DAVE-safe hybrid): answers advance and finish."""
    state = {"answers": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sessions":
            return httpx.Response(
                201,
                json={
                    "session_id": "vs3",
                    "survey_id": "campus_opinion_survey",
                    "status": "in_progress",
                    "current_question": {"question_id": "q1", "text": "Q1", "answer_type": "free_text", "options": []},
                    "tts": {"audio_path": "/data/tts/q1-gpt_sovits.wav", "duration_sec": 1.0, "provider": "gpt_sovits", "cached": False},
                },
            )
        if request.url.path == "/sessions/vs3/answers":
            state["answers"] += 1
            if state["answers"] == 1:
                return httpx.Response(
                    200,
                    json={
                        "session_id": "vs3",
                        "status": "in_progress",
                        "agent_result": _agent_result("q1"),
                        "next_question": {"question_id": "q2", "text": "Q2", "answer_type": "free_text", "options": []},
                        "tts": {"audio_path": "/data/tts/q2-gpt_sovits.wav", "duration_sec": 1.0, "provider": "gpt_sovits", "cached": False},
                    },
                )
            return httpx.Response(
                200,
                json={"session_id": "vs3", "status": "completed", "agent_result": _agent_result("q2"), "next_question": None, "tts": None},
            )
        if request.url.path == "/sessions/vs3/summary":
            return httpx.Response(
                200,
                json={"session_id": "vs3", "survey_id": "campus_opinion_survey", "status": "completed", "current_question_id": None, "response_count": 2, "responses": []},
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ai-orchestrator:8000") as client:
        manager = VoiceSurveyManager(
            client=OrchestratorClient("http://ai-orchestrator:8000", client=client),
            default_survey_id="campus_opinion_survey",
        )
        await manager.start(conversation_key="c:u", discord_user_id="123")
        assert manager.has_session("c:u") is True

        r1 = await manager.submit_text_answer(conversation_key="c:u", transcript="도서관 좌석이 더 필요합니다")
        assert r1["completed"] is False
        assert r1["audio_path"] == "/data/tts/q2-gpt_sovits.wav"  # next question voiced

        r2 = await manager.submit_text_answer(conversation_key="c:u", transcript="전반적으로 좋습니다")
        assert r2["completed"] is True

    assert manager.has_session("c:u") is False


@pytest.mark.asyncio
async def test_submit_text_answer_without_session_prompts_start() -> None:
    async with httpx.AsyncClient(base_url="http://ai-orchestrator:8000") as client:
        manager = VoiceSurveyManager(
            client=OrchestratorClient("http://ai-orchestrator:8000", client=client),
            default_survey_id="campus_opinion_survey",
        )
        result = await manager.submit_text_answer(conversation_key="none", transcript="안녕")
    assert result["completed"] is False
    assert "voice-start" in result["message"]


@pytest.mark.asyncio
async def test_client_raises_no_speech_on_422() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": "No speech detected in audio"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ai-orchestrator:8000") as client:
        oc = OrchestratorClient("http://ai-orchestrator:8000", client=client)
        with pytest.raises(NoSpeechDetected):
            await oc.submit_audio_answer(session_id="s", question_id="q1", audio_path="/x.wav")
