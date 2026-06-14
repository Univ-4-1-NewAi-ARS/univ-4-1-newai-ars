from pathlib import Path

from fastapi.testclient import TestClient

from app import main as tts_main
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


def test_local_espeak_synthesizes_wav(tmp_path, monkeypatch) -> None:
    def fake_run(command, check, capture_output, text, timeout):
        output_path = command[command.index("-w") + 1]
        tts_main._write_silence_wav(Path(output_path))

    monkeypatch.setattr(tts_main.shutil, "which", lambda name: "/usr/bin/espeak-ng")
    monkeypatch.setattr(tts_main.subprocess, "run", fake_run)
    settings = Settings(tts_provider="local_espeak", tts_dir=tmp_path)

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/synthesize",
            json={"text": "안녕하세요", "survey_id": "campus_opinion_survey", "question_id": "q1"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "local_espeak"
    assert payload["fallback_used"] is False
    assert payload["audio_path"].endswith("campus_opinion_survey-q1-ko_default-local_espeak.wav")


def test_local_piper_synthesizes_wav(tmp_path, monkeypatch) -> None:
    model_path = tmp_path / "piper-kss-korean.onnx"
    model_path.write_bytes(b"onnx")

    def fake_run(command, input, check, capture_output, text, timeout):
        output_path = command[command.index("--output_file") + 1]
        tts_main._write_silence_wav(Path(output_path))

    monkeypatch.setattr(tts_main.shutil, "which", lambda name: "/usr/bin/piper")
    monkeypatch.setattr(tts_main.subprocess, "run", fake_run)
    settings = Settings(tts_provider="local_piper", piper_model_path=model_path, tts_dir=tmp_path)

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/synthesize",
            json={"text": "안녕하세요", "survey_id": "campus_opinion_survey", "question_id": "q1"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "local_piper"
    assert payload["fallback_used"] is False
    assert payload["audio_path"].endswith("campus_opinion_survey-q1-ko_default-local_piper.wav")


def test_local_piper_falls_back_to_cached_file(tmp_path) -> None:
    settings = Settings(
        tts_provider="local_piper",
        tts_fallback_provider="cached_file",
        tts_use_cached_fallback=True,
        tts_dir=tmp_path,
    )

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/synthesize",
            json={"text": "안녕하세요", "survey_id": "campus_opinion_survey", "question_id": "q1"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "cached_file"
    assert payload["fallback_used"] is True
    assert tmp_path.joinpath("campus_opinion_survey-q1-ko_default.wav").exists()
