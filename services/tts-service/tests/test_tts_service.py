from fastapi.testclient import TestClient

from app.main import Settings, create_app


def test_health(tmp_path) -> None:
    with TestClient(create_app(Settings(tts_provider="cached_file", tts_dir=tmp_path))) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "tts-service"


def test_synthesize_creates_cached_file(tmp_path) -> None:
    with TestClient(create_app(Settings(tts_provider="cached_file", tts_dir=tmp_path))) as client:
        response = client.post(
            "/synthesize",
            json={
                "text": "현재 캠퍼스 시설에 얼마나 만족하시나요?",
                "voice": "ko_default",
                "language": "ko",
                "survey_id": "campus_opinion_survey",
                "question_id": "q1",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["audio_path"].endswith("campus_opinion_survey-q1-ko_default.wav")
    assert tmp_path.joinpath("campus_opinion_survey-q1-ko_default.wav").exists()
