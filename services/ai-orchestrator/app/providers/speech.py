from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from app.core.settings import Settings
from app.models import TTSResult, TranscriptionResult
from app.providers.mock import MockSTTProvider, MockTTSProvider


class STTProvider(ABC):
    provider_name: str

    @abstractmethod
    async def transcribe(self, audio_path: str, language: str) -> TranscriptionResult:
        raise NotImplementedError


class TTSProvider(ABC):
    provider_name: str

    @abstractmethod
    async def synthesize(self, text: str, voice: str, survey_id: str, question_id: str) -> TTSResult:
        raise NotImplementedError


class ServiceSTTProvider(STTProvider):
    provider_name = "stt-service"

    def __init__(self, base_url: str, provider: str, timeout_sec: float = 10.0, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.provider = provider
        self.timeout_sec = timeout_sec
        self.client = client

    async def transcribe(self, audio_path: str, language: str) -> TranscriptionResult:
        request = {"audio_path": audio_path, "language": language, "provider": self.provider}
        if self.client:
            response = await self.client.post(f"{self.base_url}/transcribe", json=request)
        else:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                response = await client.post(f"{self.base_url}/transcribe", json=request)
        response.raise_for_status()
        return TranscriptionResult.model_validate(response.json())


class ServiceTTSProvider(TTSProvider):
    provider_name = "tts-service"

    def __init__(self, base_url: str, provider: str, language: str, timeout_sec: float = 10.0, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.provider = provider
        self.language = language
        self.timeout_sec = timeout_sec
        self.client = client

    async def synthesize(self, text: str, voice: str, survey_id: str, question_id: str) -> TTSResult:
        request = {
            "text": text,
            "voice": voice,
            "language": self.language,
            "provider": self.provider,
            "survey_id": survey_id,
            "question_id": question_id,
        }
        if self.client:
            response = await self.client.post(f"{self.base_url}/synthesize", json=request)
        else:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                response = await client.post(f"{self.base_url}/synthesize", json=request)
        response.raise_for_status()
        return TTSResult.model_validate(response.json())


def build_stt_provider(settings: Settings) -> STTProvider:
    if settings.stt_provider == "mock":
        return MockSTTProvider()
    return ServiceSTTProvider(settings.stt_base_url, settings.stt_provider, settings.llm_timeout_sec)


def build_tts_provider(settings: Settings) -> TTSProvider:
    if settings.tts_provider == "mock":
        return MockTTSProvider()
    return ServiceTTSProvider(settings.tts_base_url, settings.tts_provider, settings.tts_language, settings.llm_timeout_sec)
