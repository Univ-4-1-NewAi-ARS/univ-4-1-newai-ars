import io
import wave
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app import main as tts_main
from app.main import Settings, create_app


def _wav_bytes(seconds: float = 0.5) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


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


def test_gpt_sovits_synthesizes_wav(tmp_path, monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, payload, timeout):
        captured["url"] = url
        captured["payload"] = payload
        return _wav_bytes(0.5)

    monkeypatch.setattr(tts_main, "_post_for_audio", fake_post)
    settings = Settings(
        tts_provider="gpt_sovits",
        gpt_sovits_ref_audio_path="/srv/ref.wav",
        gpt_sovits_ref_text="안녕하세요",
        tts_dir=tmp_path,
    )

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/synthesize",
            json={"text": "질문입니다", "language": "ko", "survey_id": "campus_opinion_survey", "question_id": "q1"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "gpt_sovits"
    assert payload["fallback_used"] is False
    assert payload["audio_path"].endswith("campus_opinion_survey-q1-ko_default-gpt_sovits.wav")
    assert tmp_path.joinpath("campus_opinion_survey-q1-ko_default-gpt_sovits.wav").exists()
    # request carries the cloning reference + target text
    assert captured["url"].endswith("/tts")
    assert captured["payload"]["ref_audio_path"] == "/srv/ref.wav"
    assert captured["payload"]["text"] == "질문입니다"
    assert captured["payload"]["text_lang"] == "ko"


def test_gpt_sovits_unconfigured_falls_back_to_cached(tmp_path) -> None:
    settings = Settings(
        tts_provider="gpt_sovits",
        gpt_sovits_ref_audio_path="",  # no reference voice configured
        tts_fallback_provider="cached_file",
        tts_use_cached_fallback=True,
        tts_dir=tmp_path,
    )

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/synthesize",
            json={"text": "질문", "survey_id": "campus_opinion_survey", "question_id": "q1"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["provider"] == "cached_file"
    assert payload["fallback_used"] is True


def test_gpt_sovits_http_error_falls_back_to_cached(tmp_path, monkeypatch) -> None:
    def boom(url, payload, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(tts_main, "_post_for_audio", boom)
    settings = Settings(
        tts_provider="gpt_sovits",
        gpt_sovits_ref_audio_path="/srv/ref.wav",
        tts_fallback_provider="cached_file",
        tts_use_cached_fallback=True,
        tts_dir=tmp_path,
    )

    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/synthesize",
            json={"text": "질문", "survey_id": "campus_opinion_survey", "question_id": "q1"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["provider"] == "cached_file"
    assert payload["fallback_used"] is True


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
