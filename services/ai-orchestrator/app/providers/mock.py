from __future__ import annotations

from pathlib import Path

from app.models import TTSResult, TranscriptionResult
from app.providers.llm import MockLLMProvider


class MockSTTProvider:
    provider_name = "mock"

    async def transcribe(self, audio_path: str, language: str) -> TranscriptionResult:
        stem = Path(audio_path).stem.lower()
        text = "만족합니다"
        if "free" in stem or "q2" in stem:
            text = "도서관 좌석이 더 필요합니다"
        return TranscriptionResult(
            text=text,
            language=language,
            confidence=0.9,
            duration_sec=2.0,
            provider=self.provider_name,
        )


class MockTTSProvider:
    provider_name = "mock"

    async def synthesize(self, text: str, voice: str, survey_id: str, question_id: str) -> TTSResult:
        safe_voice = voice.replace("/", "_")
        return TTSResult(
            audio_path=f"/data/tts/{survey_id}-{question_id}-{safe_voice}.wav",
            duration_sec=max(1.0, min(len(text) / 8.0, 8.0)),
            provider=self.provider_name,
            cached=True,
        )
