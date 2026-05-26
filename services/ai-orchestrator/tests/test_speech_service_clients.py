import httpx
import pytest

from app.providers.speech import ServiceSTTProvider, ServiceTTSProvider


@pytest.mark.asyncio
async def test_service_stt_provider_calls_transcribe() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/transcribe"
        return httpx.Response(
            200,
            json={
                "text": "만족합니다",
                "language": "ko",
                "confidence": 0.9,
                "duration_sec": 2.0,
                "provider": "mock",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://stt-service:8100") as client:
        provider = ServiceSTTProvider("http://stt-service:8100", "mock", client=client)
        result = await provider.transcribe("/data/audio/q1.wav", "ko")

    assert result.text == "만족합니다"


@pytest.mark.asyncio
async def test_service_tts_provider_calls_synthesize() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/synthesize"
        return httpx.Response(
            200,
            json={
                "audio_path": "/data/tts/campus_opinion_survey-q1-ko_default.wav",
                "duration_sec": 2.5,
                "provider": "cached_file",
                "cached": True,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://tts-service:8200") as client:
        provider = ServiceTTSProvider("http://tts-service:8200", "cached_file", "ko", client=client)
        result = await provider.synthesize("질문", "ko_default", "campus_opinion_survey", "q1")

    assert result.audio_path.endswith("campus_opinion_survey-q1-ko_default.wav")
