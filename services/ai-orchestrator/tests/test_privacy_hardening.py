from pathlib import Path

from fastapi.testclient import TestClient

from app.core.privacy import TRANSCRIPT_REDACTED_TEXT, mask_sensitive_text, normalize_participant_ref
from app.core.settings import Settings
from app.main import create_app
from conftest import SURVEY_DIR


def test_privacy_helpers_mask_secrets_and_hash_participants() -> None:
    masked = mask_sensitive_text(
        "Bearer sk-secret12345 from user@example.com and phone 010-1234-5678",
        extra_secrets=["secret12345"],
    )

    assert "sk-secret12345" not in masked
    assert "user@example.com" not in masked
    assert "010-1234-5678" not in masked
    assert normalize_participant_ref("123456789").startswith("hash:")
    assert normalize_participant_ref("discord_hash:abc123") == "discord_hash:abc123"


def test_transcript_redaction_and_audio_retention_cleanup(tmp_path: Path) -> None:
    audio_path = tmp_path / "q1.wav"
    audio_path.write_bytes(b"mock audio")
    settings = Settings(
        repository_provider="memory",
        survey_dir=SURVEY_DIR,
        stt_provider="mock",
        tts_provider="mock",
        save_transcript=False,
        save_raw_audio=True,
        raw_audio_retention_days=0,
        audio_dir=tmp_path,
        participant_hash_salt="test-salt",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        created = client.post(
            "/sessions",
            json={
                "survey_id": "campus_opinion_survey",
                "participant_ref": "123456789",
                "channel": "mock",
            },
        )
        session_id = created.json()["session_id"]
        stored_session = app.state.repository.sessions[session_id]
        assert stored_session.participant_ref.startswith("hash:")

        answer = client.post(
            f"/sessions/{session_id}/answers",
            json={"question_id": "q1", "audio_path": str(audio_path), "source": "mock"},
        )
        assert answer.status_code == 200
        assert answer.json()["agent_result"]["raw_transcript"] == TRANSCRIPT_REDACTED_TEXT
        assert app.state.repository.responses[0].agent_result.cleaned_text == TRANSCRIPT_REDACTED_TEXT
        assert len(app.state.repository.audio_records) == 1

        cleanup = client.post("/retention/audio/cleanup", params={"dry_run": "false"})
        assert cleanup.status_code == 200
        assert cleanup.json()["expired_records"] == 1
        assert cleanup.json()["deleted_files"] == 1
        assert cleanup.json()["skipped_files"] == 0
        assert not audio_path.exists()
        assert app.state.repository.audio_records == []
        assert {event["event_type"] for event in app.state.repository.audit_events} >= {
            "session_started",
            "answer_processed",
            "raw_audio_cleanup",
        }


def test_fallback_is_recorded_in_agent_log() -> None:
    settings = Settings(
        repository_provider="memory",
        survey_dir=SURVEY_DIR,
        stt_provider="mock",
        tts_provider="mock",
        llm_provider="ollama",
        llm_base_url="http://127.0.0.1:1",
        llm_use_api_fallback=False,
    )
    app = create_app(settings)

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
        response = client.post(
            f"/sessions/{session_id}/answers",
            json={"question_id": "q1", "transcript": "만족합니다", "source": "mock"},
        )

        assert response.status_code == 200
        assert app.state.repository.agent_logs[-1]["provider"] == "mock"
        assert app.state.repository.agent_logs[-1]["fallback_used"] is True
