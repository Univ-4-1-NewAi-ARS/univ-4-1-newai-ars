from fastapi.testclient import TestClient
from pathlib import Path

from app.core.settings import Settings
from app.main import create_app
from conftest import SURVEY_DIR


def test_stats_and_report_export(tmp_path) -> None:
    app = create_app(
        Settings(
            repository_provider="memory",
            survey_dir=SURVEY_DIR,
            report_dir=tmp_path,
            stt_provider="mock",
            tts_provider="mock",
        )
    )

    with TestClient(app) as client:
        created = client.post(
            "/sessions",
            json={"survey_id": "campus_opinion_survey", "participant_ref": "discord:masked-user-id", "channel": "mock"},
        ).json()
        session_id = created["session_id"]
        client.post(f"/sessions/{session_id}/answers", json={"question_id": "q1", "transcript": "만족합니다", "source": "mock"})

        stats = client.get("/surveys/campus_opinion_survey/stats")
        report = client.post("/surveys/campus_opinion_survey/reports")

    assert stats.status_code == 200
    assert stats.json()["option_counts"]["q1"]["2"] == 1
    assert report.status_code == 200
    assert tmp_path.joinpath(Path(report.json()["report_path"]).name).exists()
