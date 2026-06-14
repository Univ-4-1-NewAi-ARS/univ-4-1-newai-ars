import struct
import types
import wave

from app import main as bot_main
from app.voice_recorder import VoiceRecorder, _to_mono_16k


def _stereo_pcm(frame_count: int = 1000) -> bytes:
    """Return `frame_count` silent stereo 16-bit PCM frames (L=0, R=0)."""
    return struct.pack("<" + "hh" * frame_count, *([0, 0] * frame_count))


def test_feed_basic(tmp_path) -> None:
    rec = VoiceRecorder(audio_dir=tmp_path)
    assert not rec.has_audio

    rec.feed(b"\x01\x02" * 1000)
    rec.feed(b"")     # empty — ignored
    rec.feed(None)    # missing — ignored

    assert rec.has_audio
    assert rec.byte_count == 2000
    assert rec.duration_sec > 0


def test_write_wav_defaults_to_mono_16k(tmp_path) -> None:
    rec = VoiceRecorder(audio_dir=tmp_path)
    rec.feed(_stereo_pcm(1200))  # 1200 stereo frames @ 48k

    path = rec.write_wav("answer.wav")
    with wave.open(path) as wav:
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        # 1200 stereo frames → 1200 mono samples → every 3rd → 400 frames
        assert wav.getnframes() == 400


def test_write_wav_raw_passthrough(tmp_path) -> None:
    rec = VoiceRecorder(audio_dir=tmp_path)
    rec.feed(_stereo_pcm(600))

    path = rec.write_wav("raw.wav", mono_16k=False)
    with wave.open(path) as wav:
        assert wav.getframerate() == 48000
        assert wav.getnchannels() == 2
        assert wav.getnframes() == 600


def test_downmix_function() -> None:
    # Two stereo frames: L=100, R=200 → mono avg=150
    raw = struct.pack("<hhhh", 100, 200, 100, 200)
    mono = _to_mono_16k(raw, src_rate=48000, sample_width=2)
    # 2 mono samples, keep every 3rd → 1 sample (only index 0 survives ::3)
    samples = struct.unpack("<" + "h" * (len(mono) // 2), mono)
    assert samples[0] == 150


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
            rec.feed(_stereo_pcm(200))

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
