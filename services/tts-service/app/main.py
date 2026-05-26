from pathlib import Path
import wave

from fastapi import FastAPI
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tts_provider: str = "cached_file"
    tts_voice: str = "ko_default"
    tts_language: str = "ko"
    tts_dir: Path = Path("/data/tts")


class HealthResponse(BaseModel):
    status: str
    service: str
    provider: str


class SynthesizeRequest(BaseModel):
    text: str
    voice: str = "ko_default"
    language: str = "ko"
    provider: str | None = None
    survey_id: str = "adhoc"
    question_id: str = "question"


class SynthesizeResponse(BaseModel):
    audio_path: str
    duration_sec: float = Field(ge=0.0)
    provider: str
    cached: bool


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    app = FastAPI(title="TTS Service", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="tts-service", provider=resolved.tts_provider)

    @app.post("/synthesize", response_model=SynthesizeResponse)
    async def synthesize(request: SynthesizeRequest) -> SynthesizeResponse:
        provider = request.provider or resolved.tts_provider
        resolved.tts_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{request.survey_id}-{request.question_id}-{request.voice}.wav"
        path = resolved.tts_dir / file_name
        cached = path.exists()
        if not cached:
            _write_silence_wav(path)
        return SynthesizeResponse(
            audio_path=str(path),
            duration_sec=max(1.0, min(len(request.text) / 8.0, 8.0)),
            provider=provider,
            cached=cached,
        )

    return app


def _write_silence_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 1600)


app = create_app()
