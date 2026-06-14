from __future__ import annotations

import wave
from pathlib import Path

# Discord voice receive delivers decoded PCM as 48kHz, 16-bit, stereo.
DISCORD_SAMPLE_RATE = 48000
DISCORD_CHANNELS = 2
DISCORD_SAMPLE_WIDTH = 2


class VoiceRecorder:
    """Buffer decoded PCM for one participant and write it as a wav file.

    Kept independent of discord.py so the buffering and wav encoding can be
    unit tested without a live voice connection. The discord voice-receive
    sink only needs to call ``feed`` with each decoded PCM chunk.
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

    def write_wav(self, filename: str) -> str:
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        path = self.audio_dir / filename
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(self.sample_width)
            wav.setframerate(self.sample_rate)
            wav.writeframes(b"".join(self._chunks))
        return str(path)

    def reset(self) -> None:
        self._chunks.clear()
