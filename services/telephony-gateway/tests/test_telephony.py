from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.main import Settings, create_app, participant_ref_from_phone
from app.orchestrator_client import OrchestratorClient


SETTINGS = Settings(orchestrator_base_url="http://orchestrator")

# Minimal 3-question script mirroring campus_opinion_survey: q1 -> q2 -> completed.
_QUESTIONS = {
    "q1": {"question_id": "q1", "text": "현재 캠퍼스 시설에 얼마나 만족하시나요?", "answer_type": "single_choice", "options": []},
    "q2": {"question_id": "q2", "text": "가장 개선이 필요한 영역은 무엇인가요?", "answer_type": "free_text", "options": []},
}


def _agent_result(question_id: str) -> dict:
    return {
        "question_id": question_id,
        "raw_transcript": "응답",
        "cleaned_text": "응답",
        "answer_type": "free_text",
        "selected_option": None,
        "confidence": 0.9,
        "sentiment": "neutral",
        "keywords": [],
        "needs_retry": False,
        "review_required": False,
        "reason": "ok",
    }


def _mock_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/sessions":
        body = request.read().decode()
        # Assert the gateway sends a hashed participant_ref and phone channel.
        assert '"channel": "phone"' in body or '"channel":"phone"' in body
        assert "phone:" in body
        return httpx.Response(
            201,
            json={
                "session_id": "session-1",
                "survey_id": "campus_opinion_survey",
                "status": "in_progress",
                "current_question": _QUESTIONS["q1"],
                "tts": {"audio_path": "/data/tts/q1.wav", "duration_sec": 1.0, "provider": "local_espeak"},
            },
        )
    if path.endswith("/answers"):
        body = request.read().decode()
        assert '"source": "phone"' in body or '"source":"phone"' in body
        if '"question_id": "q1"' in body or '"question_id":"q1"' in body:
            return httpx.Response(
                200,
                json={
                    "session_id": "session-1",
                    "status": "in_progress",
                    "agent_result": _agent_result("q1"),
                    "next_question": _QUESTIONS["q2"],
                    "tts": {"audio_path": "/data/tts/q2.wav", "duration_sec": 1.0, "provider": "local_espeak"},
                },
            )
        # q2 answer -> survey completes.
        return httpx.Response(
            200,
            json={
                "session_id": "session-1",
                "status": "completed",
                "agent_result": _agent_result("q2"),
                "next_question": None,
                "tts": None,
            },
        )
    return httpx.Response(404, json={"detail": "not found"})


def _build_client(settings: Settings | None = None) -> TestClient:
    resolved = settings or SETTINGS
    transport = httpx.MockTransport(_mock_handler)
    async_client = httpx.AsyncClient(transport=transport)
    orchestrator = OrchestratorClient(resolved.orchestrator_base_url, client=async_client)
    app = create_app(resolved, client=orchestrator)
    return TestClient(app)


def test_participant_ref_is_hashed() -> None:
    ref = participant_ref_from_phone("+821012345678")
    assert ref.startswith("phone:")
    assert len(ref) == len("phone:") + 12
    assert "821012345678" not in ref  # raw number is not leaked


def test_health() -> None:
    with TestClient(create_app(SETTINGS)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "telephony-gateway"}


def test_incoming_returns_twiml_with_first_question_and_gather() -> None:
    with _build_client() as client:
        response = client.post(
            "/voice/incoming",
            data={"CallSid": "CA-test-1", "From": "+821012345678"},
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    text = response.text
    assert "<Response>" in text and "</Response>" in text
    assert "현재 캠퍼스 시설에 얼마나 만족하시나요?" in text  # question 1 by default uses <Say>
    assert "<Say" in text
    assert '<Gather input="speech"' in text
    assert 'action="/voice/answer"' in text


def test_answer_advances_then_hangs_up() -> None:
    with _build_client() as client:
        # Establish call state.
        client.post("/voice/incoming", data={"CallSid": "CA-test-2", "From": "+821011112222"})

        # Answer q1 -> should advance to q2 with another Gather, no Hangup yet.
        r1 = client.post("/voice/answer", data={"CallSid": "CA-test-2", "SpeechResult": "매우 만족합니다"})
        assert r1.status_code == 200
        assert "가장 개선이 필요한 영역은 무엇인가요?" in r1.text
        assert "<Gather" in r1.text
        assert "<Hangup/>" not in r1.text

        # Answer q2 -> survey completes with a completion message + Hangup.
        r2 = client.post("/voice/answer", data={"CallSid": "CA-test-2", "SpeechResult": "주차 공간"})
        assert r2.status_code == 200
        assert "<Hangup/>" in r2.text
        assert "<Gather" not in r2.text


def test_answer_without_call_state_hangs_up() -> None:
    with _build_client() as client:
        response = client.post("/voice/answer", data={"CallSid": "unknown", "SpeechResult": "안녕"})
    assert response.status_code == 200
    assert "<Hangup/>" in response.text


def test_empty_speech_reprompts_without_hangup() -> None:
    with _build_client() as client:
        client.post("/voice/incoming", data={"CallSid": "CA-test-3", "From": "+821033334444"})
        response = client.post("/voice/answer", data={"CallSid": "CA-test-3", "SpeechResult": ""})
    assert response.status_code == 200
    assert "<Gather" in response.text
    assert "<Hangup/>" not in response.text


def test_play_audio_mode_uses_play_verb() -> None:
    settings = Settings(
        orchestrator_base_url="http://orchestrator",
        telephony_use_tts_audio=True,
        public_base_url="https://example.ngrok.app",
    )
    with _build_client(settings) as client:
        response = client.post("/voice/incoming", data={"CallSid": "CA-test-4", "From": "+821055556666"})
    assert response.status_code == 200
    assert "<Play>https://example.ngrok.app/media/q1.wav</Play>" in response.text
    assert "<Say" not in response.text


def test_media_rejects_path_traversal() -> None:
    with TestClient(create_app(SETTINGS)) as client:
        response = client.get("/media/..%2f..%2fetc%2fpasswd")
    assert response.status_code in (400, 404)
