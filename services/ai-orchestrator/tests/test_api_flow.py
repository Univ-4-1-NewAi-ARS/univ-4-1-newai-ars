from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app
from conftest import SURVEY_DIR


def test_text_flow_stores_responses_and_completes() -> None:
    app = create_app(Settings(repository_provider="memory", survey_dir=SURVEY_DIR, stt_provider="mock", tts_provider="mock"))

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["repository"] == "memory"

        created = client.post(
            "/sessions",
            json={
                "survey_id": "campus_opinion_survey",
                "participant_ref": "discord:masked-user-id",
                "channel": "mock",
            },
        )
        assert created.status_code == 201
        session = created.json()
        assert session["current_question"]["question_id"] == "q1"
        session_id = session["session_id"]

        answer_1 = client.post(
            f"/sessions/{session_id}/answers",
            json={"question_id": "q1", "transcript": "만족합니다", "source": "mock"},
        )
        assert answer_1.status_code == 200
        assert answer_1.json()["agent_result"]["selected_option"] == "2"
        assert answer_1.json()["next_question"]["question_id"] == "q2"

        answer_2 = client.post(
            f"/sessions/{session_id}/answers",
            json={"question_id": "q2", "transcript": "도서관 좌석이 더 필요합니다", "source": "mock"},
        )
        assert answer_2.status_code == 200
        assert answer_2.json()["next_question"]["question_id"] == "q3"

        answer_3 = client.post(
            f"/sessions/{session_id}/answers",
            json={"question_id": "q3", "transcript": "전반적으로 좋습니다", "source": "mock"},
        )
        assert answer_3.status_code == 200
        assert answer_3.json()["status"] == "completed"
        assert answer_3.json()["next_question"] is None

        summary = client.get(f"/sessions/{session_id}/summary")
        assert summary.status_code == 200
        assert summary.json()["response_count"] == 3
        assert summary.json()["status"] == "completed"


def test_audio_path_uses_mock_stt() -> None:
    app = create_app(Settings(repository_provider="memory", survey_dir=SURVEY_DIR, stt_provider="mock", tts_provider="mock"))

    with TestClient(app) as client:
        created = client.post(
            "/sessions",
            json={
                "survey_id": "campus_opinion_survey",
                "participant_ref": "discord:masked-user-id",
                "channel": "mock",
            },
        )
        session_id = created.json()["session_id"]

        answer = client.post(
            f"/sessions/{session_id}/answers",
            json={"question_id": "q1", "audio_path": "/data/audio/q1.wav", "source": "mock"},
        )
        assert answer.status_code == 200
        assert answer.json()["agent_result"]["raw_transcript"] == "만족합니다"


def test_audit_events_endpoint_lists_recent_events() -> None:
    app = create_app(Settings(repository_provider="memory", survey_dir=SURVEY_DIR, stt_provider="mock", tts_provider="mock"))

    with TestClient(app) as client:
        empty = client.get("/audit/events")
        assert empty.status_code == 200
        assert empty.json() == {"count": 0, "events": []}

        created = client.post(
            "/sessions",
            json={"survey_id": "campus_opinion_survey", "participant_ref": "discord:masked-user-id", "channel": "mock"},
        )
        session_id = created.json()["session_id"]
        client.post(
            f"/sessions/{session_id}/answers",
            json={"question_id": "q1", "transcript": "만족합니다", "source": "mock"},
        )

        events = client.get("/audit/events?limit=10")
        assert events.status_code == 200
        payload = events.json()
        assert payload["count"] >= 2
        types = [event["event_type"] for event in payload["events"]]
        # most recent first
        assert types[0] == "answer_processed"
        assert "session_started" in types


def test_survey_insights_synthesizes_opinions() -> None:
    app = create_app(
        Settings(repository_provider="memory", survey_dir=SURVEY_DIR, llm_provider="mock", stt_provider="mock", tts_provider="mock")
    )

    with TestClient(app) as client:
        created = client.post(
            "/sessions",
            json={"survey_id": "campus_opinion_survey", "participant_ref": "discord:masked-user-id", "channel": "mock"},
        )
        session_id = created.json()["session_id"]
        client.post(
            f"/sessions/{session_id}/answers",
            json={"question_id": "q1", "transcript": "만족합니다", "source": "mock"},
        )
        client.post(
            f"/sessions/{session_id}/answers",
            json={"question_id": "q2", "transcript": "도서관 좌석이 더 필요합니다", "source": "mock"},
        )

        insights = client.get("/surveys/campus_opinion_survey/insights")
        assert insights.status_code == 200
        payload = insights.json()
        assert payload["response_count"] >= 2
        assert isinstance(payload["keyword_counts"], dict)

        by_id = {q["question_id"]: q for q in payload["questions"]}
        # single_choice option_counts use human labels, not raw ids
        assert by_id["q1"]["option_counts"].get("만족", 0) >= 1
        # free_text opinions carry the actual opinion text
        q2 = by_id["q2"]
        assert q2["answer_type"] == "free_text"
        assert any("도서관 좌석" in opinion["text"] for opinion in q2["opinions"])


def test_runtime_provider_status() -> None:
    app = create_app(
        Settings(
            repository_provider="memory",
            survey_dir=SURVEY_DIR,
            llm_provider="ollama",
            llm_model="gemma3:4b",
            stt_provider="local_whisper",
            tts_provider="local_espeak",
        )
    )

    with TestClient(app) as client:
        response = client.get("/runtime/providers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["llm"]["provider"] == "ollama"
    assert payload["llm"]["mock_fallback_enabled"] is True
    assert payload["stt"]["provider"] == "local_whisper"
    assert payload["tts"]["provider"] == "local_espeak"
