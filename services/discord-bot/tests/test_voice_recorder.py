import types
import wave

from app import main as bot_main
from app.voice_recorder import VoiceRecorder


def test_feed_and_wav_roundtrip(tmp_path) -> None:
    rec = VoiceRecorder(audio_dir=tmp_path)
    assert not rec.has_audio

    rec.feed(b"\x01\x02" * 1000)
    rec.feed(b"")     # empty frame ignored
    rec.feed(None)    # missing frame ignored

    assert rec.has_audio
    assert rec.byte_count == 2000

    path = rec.write_wav("answer.wav")
    with wave.open(path) as wav:
        assert wav.getframerate() == 48000
        assert wav.getnchannels() == 2
        assert wav.getsampwidth() == 2
        assert wav.getnframes() == 500  # 2000 bytes / (2 channels * 2 width)
    assert rec.duration_sec > 0


def test_reset_clears_buffer(tmp_path) -> None:
    rec = VoiceRecorder(audio_dir=tmp_path)
    rec.feed(b"abcd")
    rec.reset()
    assert not rec.has_audio
    assert rec.byte_count == 0


async def test_capture_stops_on_silence(tmp_path, monkeypatch) -> None:
    rec = VoiceRecorder(audio_dir=tmp_path)
    settings = types.SimpleNamespace(voice_max_record_sec=10.0, voice_silence_timeout_sec=1.0)
    active = types.SimpleNamespace(session_id="s1", current_question_id="q1")

    calls = {"n": 0}

    async def fake_sleep(_seconds: float) -> None:
        calls["n"] += 1
        if calls["n"] <= 3:  # audio arrives for the first three polls
            rec.feed(b"\x00\x01" * 100)

    monkeypatch.setattr(bot_main.asyncio, "sleep", fake_sleep)
    path = await bot_main._capture_until_silence(rec, settings, active)

    assert path is not None
    assert path.endswith("s1-q1.wav")
    assert rec.has_audio


async def test_capture_returns_none_without_audio(tmp_path, monkeypatch) -> None:
    rec = VoiceRecorder(audio_dir=tmp_path)
    settings = types.SimpleNamespace(voice_max_record_sec=2.0, voice_silence_timeout_sec=1.0)
    active = types.SimpleNamespace(session_id="s", current_question_id="q")

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(bot_main.asyncio, "sleep", fake_sleep)
    path = await bot_main._capture_until_silence(rec, settings, active)

    assert path is None
