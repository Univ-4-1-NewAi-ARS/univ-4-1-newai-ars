from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    stt_provider: str = "mock"
    stt_language: str = "ko"
    transcript_dir: Path = Path("/data/transcripts")


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


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    app = FastAPI(title="STT Service", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="stt-service", provider=resolved.stt_provider)

    @app.post("/transcribe", response_model=TranscribeResponse)
    async def transcribe(request: TranscribeRequest) -> TranscribeResponse:
        provider = request.provider or resolved.stt_provider
        text = _transcript_for_audio(request.audio_path, resolved.transcript_dir, provider)
        return TranscribeResponse(
            text=text,
            language=request.language or resolved.stt_language,
            confidence=0.9 if provider in {"mock", "file"} else 0.5,
            duration_sec=2.0,
            provider=provider,
        )

    return app


def _transcript_for_audio(audio_path: str, transcript_dir: Path, provider: str) -> str:
    stem = Path(audio_path).stem
    transcript_file = transcript_dir / f"{stem}.txt"
    if provider == "file" and transcript_file.exists():
        return transcript_file.read_text(encoding="utf-8").strip()
    if "q2" in stem.lower() or "free" in stem.lower():
        return "도서관 좌석이 더 필요합니다"
    if "q3" in stem.lower():
        return "전반적으로 좋습니다"
    return "만족합니다"


app = create_app()
