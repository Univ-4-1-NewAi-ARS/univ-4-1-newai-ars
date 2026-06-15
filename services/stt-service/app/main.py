from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderUnavailable(RuntimeError):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    stt_provider: str = "local_whisper"
    stt_model: str = "small"
    stt_language: str = "ko"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"
    stt_model_dir: Path = Path("/models/whisper")
    stt_use_mock_fallback: bool = True
    transcript_dir: Path = Path("/data/transcripts")
    # Whisper decoding quality / anti-hallucination knobs. VAD trims silence so
    # whisper does not hallucinate filler ("구독&좋아요&댓글...") on quiet audio;
    # no_speech_threshold + condition_on_previous_text=False further suppress it.
    stt_beam_size: int = 5
    stt_vad_filter: bool = True
    stt_vad_min_silence_ms: int = 500
    stt_no_speech_threshold: float = 0.6
    stt_condition_on_previous_text: bool = False
    stt_temperature: float = 0.0


class HealthResponse(BaseModel):
    status: str
    service: str
    provider: str


class TranscribeRequest(BaseModel):
    audio_path: str
    language: str = "ko"
    provider: str | None = None


class TranscribeResponse(BaseModel):
    text: str
    language: str
    confidence: float = Field(ge=0.0, le=1.0)
    duration_sec: float | None = None
    provider: str
    fallback_used: bool = False


class STTProvider(Protocol):
    provider_name: str

    def transcribe(self, audio_path: str, language: str, settings: Settings) -> TranscribeResponse:
        ...


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    app = FastAPI(title="STT Service", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="stt-service", provider=resolved.stt_provider)

    @app.post("/transcribe", response_model=TranscribeResponse)
    async def transcribe(request: TranscribeRequest) -> TranscribeResponse:
        provider = request.provider or resolved.stt_provider
        return transcribe_with_fallback(provider, request.audio_path, request.language or resolved.stt_language, resolved)

    return app


def transcribe_with_fallback(provider: str, audio_path: str, language: str, settings: Settings) -> TranscribeResponse:
    providers = _fallback_chain(provider, settings)
    last_error: Exception | None = None

    for index, candidate in enumerate(providers):
        try:
            response = _provider_for(candidate).transcribe(audio_path, language, settings)
            return response.model_copy(update={"fallback_used": index > 0})
        except ProviderUnavailable as exc:
            last_error = exc
            continue

    raise ProviderUnavailable(str(last_error) if last_error else "No STT provider could transcribe audio")


def _fallback_chain(provider: str, settings: Settings) -> list[str]:
    normalized = provider.lower()
    chain = [normalized]
    if normalized != "file":
        chain.append("file")
    if settings.stt_use_mock_fallback and normalized != "mock":
        chain.append("mock")
    return list(dict.fromkeys(chain))


def _provider_for(provider: str) -> STTProvider:
    if provider == "mock":
        return MockSTTProvider()
    if provider == "file":
        return FileSTTProvider()
    if provider == "local_whisper":
        return LocalWhisperSTTProvider()
    raise ProviderUnavailable(f"Unsupported STT provider: {provider}")


class MockSTTProvider:
    provider_name = "mock"

    def transcribe(self, audio_path: str, language: str, settings: Settings) -> TranscribeResponse:
        text = _mock_transcript_for_audio(audio_path)
        return TranscribeResponse(text=text, language=language, confidence=0.9, duration_sec=2.0, provider=self.provider_name)


class FileSTTProvider:
    provider_name = "file"

    def transcribe(self, audio_path: str, language: str, settings: Settings) -> TranscribeResponse:
        stem = Path(audio_path).stem
        transcript_file = settings.transcript_dir / f"{stem}.txt"
        if not transcript_file.exists():
            raise ProviderUnavailable(f"Transcript fixture not found: {transcript_file}")
        text = transcript_file.read_text(encoding="utf-8").strip()
        if not text:
            raise ProviderUnavailable(f"Transcript fixture was empty: {transcript_file}")
        return TranscribeResponse(text=text, language=language, confidence=0.95, duration_sec=None, provider=self.provider_name)


class LocalWhisperSTTProvider:
    provider_name = "local_whisper"

    def transcribe(self, audio_path: str, language: str, settings: Settings) -> TranscribeResponse:
        path = Path(audio_path)
        if not path.exists():
            raise ProviderUnavailable(f"Audio file not found: {audio_path}")
        try:
            model = _load_whisper_model(settings.stt_model, settings.stt_device, settings.stt_compute_type, str(settings.stt_model_dir))
            transcribe_kwargs = {
                "language": language,
                "beam_size": settings.stt_beam_size,
                "temperature": settings.stt_temperature,
                "no_speech_threshold": settings.stt_no_speech_threshold,
                "condition_on_previous_text": settings.stt_condition_on_previous_text,
            }
            if settings.stt_vad_filter:
                transcribe_kwargs["vad_filter"] = True
                transcribe_kwargs["vad_parameters"] = {"min_silence_duration_ms": settings.stt_vad_min_silence_ms}
            segments, info = model.transcribe(str(path), **transcribe_kwargs)
            text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        except Exception as exc:
            raise ProviderUnavailable(f"local_whisper failed: {exc}") from exc
        if not text:
            raise ProviderUnavailable("local_whisper returned an empty transcript")
        confidence = float(getattr(info, "language_probability", 0.5) or 0.5)
        duration_sec = getattr(info, "duration", None)
        return TranscribeResponse(text=text, language=language, confidence=confidence, duration_sec=duration_sec, provider=self.provider_name)


@lru_cache(maxsize=4)
def _load_whisper_model(model: str, device: str, compute_type: str, download_root: str):
    from faster_whisper import WhisperModel

    return WhisperModel(model, device=device, compute_type=compute_type, download_root=download_root)


def _mock_transcript_for_audio(audio_path: str) -> str:
    stem = Path(audio_path).stem
    if "q2" in stem.lower() or "free" in stem.lower():
        return "도서관 좌석이 더 필요합니다"
    if "q3" in stem.lower():
        return "전반적으로 좋습니다"
    return "만족합니다"


app = create_app()
