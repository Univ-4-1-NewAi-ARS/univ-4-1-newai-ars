from fastapi.testclient import TestClient

from app.main import Settings, create_app


def test_health() -> None:
    with TestClient(create_app(Settings(stt_provider="mock"))) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "stt-service"


def test_mock_transcribe() -> None:
    with TestClient(create_app(Settings(stt_provider="mock"))) as client:
        response = client.post("/transcribe", json={"audio_path": "/data/audio/q1.wav", "language": "ko"})

    assert response.status_code == 200
    assert response.json()["text"] == "만족합니다"
    assert response.json()["provider"] == "mock"
