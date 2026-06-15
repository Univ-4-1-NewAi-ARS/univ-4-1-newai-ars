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


def test_file_transcribe(tmp_path) -> None:
    tmp_path.joinpath("q1.txt").write_text("파일 기반 응답입니다", encoding="utf-8")
    settings = Settings(stt_provider="file", transcript_dir=tmp_path)

    with TestClient(create_app(settings)) as client:
        response = client.post("/transcribe", json={"audio_path": "/data/audio/q1.wav", "language": "ko"})

    assert response.status_code == 200
    assert response.json()["text"] == "파일 기반 응답입니다"
    assert response.json()["provider"] == "file"


def test_local_whisper_falls_back_to_file(tmp_path) -> None:
    tmp_path.joinpath("q1.txt").write_text("fallback transcript", encoding="utf-8")
    settings = Settings(stt_provider="local_whisper", transcript_dir=tmp_path, stt_use_mock_fallback=True)

    with TestClient(create_app(settings)) as client:
        response = client.post("/transcribe", json={"audio_path": "/missing/q1.wav", "language": "ko"})

    assert response.status_code == 200
    assert response.json()["text"] == "fallback transcript"
    assert response.json()["provider"] == "file"
    assert response.json()["fallback_used"] is True


def test_local_whisper_passes_vad_and_antihallucination_kwargs(monkeypatch, tmp_path) -> None:
    import app.main as m

    captured: dict = {}

    class _Seg:
        text = "안녕하세요"

    class _Info:
        language_probability = 0.99
        duration = 1.2

    class _FakeModel:
        def transcribe(self, audio, **kwargs):
            captured.update(kwargs)
            return [_Seg()], _Info()

    monkeypatch.setattr(m, "_load_whisper_model", lambda *a, **k: _FakeModel())
    audio = tmp_path / "answer.wav"
    audio.write_bytes(b"RIFFfake-wav-bytes")
    settings = Settings(stt_provider="local_whisper", stt_use_mock_fallback=False)

    with TestClient(create_app(settings)) as client:
        response = client.post("/transcribe", json={"audio_path": str(audio), "language": "ko"})

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "안녕하세요"
    assert body["provider"] == "local_whisper"
    assert captured.get("vad_filter") is True
    assert captured["vad_parameters"]["min_silence_duration_ms"] == 500
    assert captured.get("no_speech_threshold") == 0.6
    assert captured.get("condition_on_previous_text") is False


def test_local_whisper_falls_back_to_mock_when_no_file() -> None:
    settings = Settings(stt_provider="local_whisper", stt_use_mock_fallback=True)

    with TestClient(create_app(settings)) as client:
        response = client.post("/transcribe", json={"audio_path": "/missing/q1.wav", "language": "ko"})

    assert response.status_code == 200
    assert response.json()["text"] == "만족합니다"
    assert response.json()["provider"] == "mock"
    assert response.json()["fallback_used"] is True
