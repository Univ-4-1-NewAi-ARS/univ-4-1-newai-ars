from __future__ import annotations

import array
import wave
from pathlib import Path

# Discord voice receive delivers decoded PCM as 48kHz, 16-bit, stereo.
DISCORD_SAMPLE_RATE = 48000
DISCORD_CHANNELS = 2
DISCORD_SAMPLE_WIDTH = 2

# Whisper works best at 16kHz mono.
WHISPER_SAMPLE_RATE = 16000
WHISPER_CHANNELS = 1


class VoiceRecorder:
    """Buffer decoded PCM for one participant and write it as a wav file.

    Kept independent of discord.py so the buffering and wav encoding can be
    unit tested without a live voice connection. The discord voice-receive
    sink only needs to call ``feed`` with each decoded PCM chunk.

    ``write_wav`` downmixes stereo→mono and resamples to 16 kHz before
    writing so whisper receives a file in its preferred format.
    """

    def __init__(
        self,
        *,
        audio_dir: Path | str,
        sample_rate: int = DISCORD_SAMPLE_RATE,
        channels: int = DISCORD_CHANNELS,
        sample_width: int = DISCORD_SAMPLE_WIDTH,
    ) -> None:
        self.audio_dir = Path(audio_dir)
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self._chunks: list[bytes] = []

    def feed(self, pcm: bytes | None) -> None:
        if pcm:
            self._chunks.append(bytes(pcm))

    @property
    def byte_count(self) -> int:
        return sum(len(chunk) for chunk in self._chunks)

    @property
    def has_audio(self) -> bool:
        return self.byte_count > 0

    @property
    def duration_sec(self) -> float:
        frame_bytes = self.sample_rate * self.channels * self.sample_width
        return self.byte_count / frame_bytes if frame_bytes else 0.0

    def write_wav(self, filename: str, *, mono_16k: bool = True) -> str:
        """Write buffered PCM as wav. If mono_16k=True (default), downmix
        stereo→mono and resample 48kHz→16kHz before writing."""
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        path = self.audio_dir / filename
        raw = b"".join(self._chunks)

        if mono_16k and self.channels == 2 and self.sample_rate == DISCORD_SAMPLE_RATE:
            raw = _to_mono_16k(raw, self.sample_rate, self.sample_width)
            out_rate = WHISPER_SAMPLE_RATE
            out_channels = WHISPER_CHANNELS
        else:
            out_rate = self.sample_rate
            out_channels = self.channels

        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(out_channels)
            wav.setsampwidth(self.sample_width)
            wav.setframerate(out_rate)
            wav.writeframes(raw)
        return str(path)

    def reset(self) -> None:
        self._chunks.clear()


def _to_mono_16k(raw: bytes, src_rate: int, sample_width: int) -> bytes:
    """Downmix stereo 16-bit PCM to mono and resample to 16 kHz.

    Uses integer averaging for downmix and nearest-sample for resample —
    fast, dependency-free, good enough for speech recognition.
    """
    samples = array.array("h", raw)  # signed 16-bit
    # stereo → mono: average L + R
    mono = array.array("h", (
        (samples[i] + samples[i + 1]) >> 1
        for i in range(0, len(samples) - 1, 2)
    ))
    # resample: keep every nth sample
    ratio = src_rate // WHISPER_SAMPLE_RATE  # 48000 // 16000 = 3
    resampled = array.array("h", mono[::ratio])
    return resampled.tobytes()
