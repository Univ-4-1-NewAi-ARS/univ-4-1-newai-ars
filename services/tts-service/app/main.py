from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import wave

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderUnavailable(RuntimeError):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tts_provider: str = "local_espeak"
    tts_fallback_provider: str = "cached_file"
    tts_use_cached_fallback: bool = True
    tts_cache_enabled: bool = True
    tts_voice: str = "ko_default"
    tts_espeak_voice: str = "ko"
    tts_language: str = "ko"
    tts_dir: Path = Path("/data/tts")
    piper_bin: str = "piper"
    piper_model_path: Path = Path("/models/piper/piper-kss-korean.onnx")
    # GPT-SoVITS: high-quality voice-cloning TTS via its api_v2 server. The ref
    # audio + transcript define the cloned voice; paths are resolved on the
    # GPT-SoVITS server, not here. Unconfigured/unreachable -> graceful fallback.
    gpt_sovits_base_url: str = "http://host.docker.internal:9880"
    gpt_sovits_ref_audio_path: str = ""
    gpt_sovits_ref_text: str = ""
    gpt_sovits_ref_lang: str = "ko"
    gpt_sovits_text_lang: str = "ko"
    gpt_sovits_text_split: str = "cut5"
    gpt_sovits_speed: float = 1.0
    gpt_sovits_timeout_sec: float = 60.0


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
    fallback_used: bool = False


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    app = FastAPI(title="TTS Service", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="tts-service", provider=resolved.tts_provider)

    @app.post("/synthesize", response_model=SynthesizeResponse)
    async def synthesize(request: SynthesizeRequest) -> SynthesizeResponse:
        provider = request.provider or resolved.tts_provider
        return synthesize_with_fallback(provider, request, resolved)

    return app


def synthesize_with_fallback(provider: str, request: SynthesizeRequest, settings: Settings) -> SynthesizeResponse:
    providers = _fallback_chain(provider, settings)
    last_error: Exception | None = None

    for index, candidate in enumerate(providers):
        try:
            response = _synthesize_with_provider(candidate, request, settings)
            return response.model_copy(update={"fallback_used": index > 0})
        except ProviderUnavailable as exc:
            last_error = exc
            continue

    raise ProviderUnavailable(str(last_error) if last_error else "No TTS provider could synthesize audio")


def _fallback_chain(provider: str, settings: Settings) -> list[str]:
    normalized = provider.lower()
    chain = [normalized]
    fallback = settings.tts_fallback_provider.lower()
    if fallback and fallback != normalized:
        chain.append(fallback)
    if settings.tts_use_cached_fallback and normalized != "cached_file":
        chain.append("cached_file")
    return list(dict.fromkeys(chain))


def _synthesize_with_provider(provider: str, request: SynthesizeRequest, settings: Settings) -> SynthesizeResponse:
    settings.tts_dir.mkdir(parents=True, exist_ok=True)
    path = settings.tts_dir / _file_name(request, provider)
    cached = path.exists()
    duration_sec = max(1.0, min(len(request.text) / 8.0, 8.0))

    if provider == "cached_file":
        if not cached:
            _write_silence_wav(path)
        return SynthesizeResponse(audio_path=str(path), duration_sec=duration_sec, provider=provider, cached=cached)

    if settings.tts_cache_enabled and cached:
        return SynthesizeResponse(audio_path=str(path), duration_sec=duration_sec, provider=provider, cached=True)

    if provider == "local_espeak":
        _run_espeak(request.text, path, settings)
        return SynthesizeResponse(audio_path=str(path), duration_sec=duration_sec, provider=provider, cached=False)

    if provider == "local_piper":
        _run_piper(request.text, path, settings)
        return SynthesizeResponse(audio_path=str(path), duration_sec=duration_sec, provider=provider, cached=False)

    if provider == "gpt_sovits":
        _run_gpt_sovits(request.text, path, request.language, settings)
        return SynthesizeResponse(
            audio_path=str(path),
            duration_sec=_wav_duration(path) or duration_sec,
            provider=provider,
            cached=False,
        )

    raise ProviderUnavailable(f"Unsupported TTS provider: {provider}")


def _file_name(request: SynthesizeRequest, provider: str) -> str:
    if provider == "cached_file":
        return f"{request.survey_id}-{request.question_id}-{request.voice}.wav"
    return f"{request.survey_id}-{request.question_id}-{request.voice}-{provider}.wav"


def _run_espeak(text: str, path: Path, settings: Settings) -> None:
    if not shutil.which("espeak-ng"):
        raise ProviderUnavailable("espeak-ng binary is not installed")
    command = ["espeak-ng", "-v", settings.tts_espeak_voice, "-w", str(path), text]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
    except subprocess.CalledProcessError as exc:
        raise ProviderUnavailable(f"local_espeak failed: {exc.stderr.strip() or exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProviderUnavailable("local_espeak timed out") from exc


def _run_piper(text: str, path: Path, settings: Settings) -> None:
    piper_bin = shutil.which(settings.piper_bin) or (settings.piper_bin if Path(settings.piper_bin).exists() else None)
    if not piper_bin:
        raise ProviderUnavailable("piper binary is not installed")
    if not settings.piper_model_path.exists():
        raise ProviderUnavailable(f"piper model not found: {settings.piper_model_path}")
    command = [piper_bin, "--model", str(settings.piper_model_path), "--output_file", str(path)]
    try:
        subprocess.run(command, input=text, check=True, capture_output=True, text=True, timeout=30)
    except subprocess.CalledProcessError as exc:
        raise ProviderUnavailable(f"local_piper failed: {exc.stderr.strip() or exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProviderUnavailable("local_piper timed out") from exc


def _run_gpt_sovits(text: str, path: Path, language: str, settings: Settings) -> None:
    """Synthesize via a GPT-SoVITS api_v2 server and save the returned wav.

    The reference audio + transcript (which define the cloned voice) live on the
    GPT-SoVITS server; we only pass their server-side path. Any failure raises
    ProviderUnavailable so the espeak/cached fallback chain takes over.
    """
    if not settings.gpt_sovits_ref_audio_path:
        raise ProviderUnavailable("gpt_sovits reference audio is not configured (GPT_SOVITS_REF_AUDIO_PATH)")

    payload = {
        "text": text,
        "text_lang": (language or settings.gpt_sovits_text_lang).lower(),
        "ref_audio_path": settings.gpt_sovits_ref_audio_path,
        "prompt_text": settings.gpt_sovits_ref_text,
        "prompt_lang": settings.gpt_sovits_ref_lang.lower(),
        "text_split_method": settings.gpt_sovits_text_split,
        "speed_factor": settings.gpt_sovits_speed,
        "media_type": "wav",
        "streaming_mode": False,
    }
    url = settings.gpt_sovits_base_url.rstrip("/") + "/tts"
    try:
        audio = _post_for_audio(url, payload, settings.gpt_sovits_timeout_sec)
    except httpx.HTTPError as exc:
        raise ProviderUnavailable(f"gpt_sovits request failed: {exc}") from exc
    if not audio:
        raise ProviderUnavailable("gpt_sovits returned empty audio")
    path.write_bytes(audio)


def _post_for_audio(url: str, payload: dict, timeout: float) -> bytes:
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.content


def _wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return frames / float(rate) if rate else None
    except Exception:
        return None


def _write_silence_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 1600)


app = create_app()
