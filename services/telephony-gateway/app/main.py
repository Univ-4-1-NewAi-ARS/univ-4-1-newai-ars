from __future__ import annotations

import os
from hashlib import sha256
from xml.sax.saxutils import escape as xml_escape

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.orchestrator_client import NoSpeechDetected, OrchestratorClient


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    orchestrator_base_url: str = "http://ai-orchestrator:8000"
    # Answer submission triggers LLM analysis on the orchestrator (slow on CPU).
    orchestrator_timeout_sec: float = 120.0
    default_survey_id: str = "campus_opinion_survey"
    # Shared TTS output dir mounted from the orchestrator/tts-service.
    tts_dir: str = "/data/tts"
    # Public HTTPS base URL of this gateway (e.g. an ngrok tunnel). Required for
    # <Play> audio playback so Twilio can fetch the wav over the internet.
    public_base_url: str = ""
    # When true (and public_base_url set), play orchestrator TTS audio via <Play>
    # instead of Twilio's built-in <Say> voice.
    telephony_use_tts_audio: bool = False
    # BCP-47 language for <Say>/<Gather> speech recognition.
    language: str = "ko-KR"


class CallState:
    """Per-call survey state, keyed by Twilio CallSid (mirrors discord conversation_key)."""

    __slots__ = ("session_id", "current_question_id")

    def __init__(self, session_id: str, current_question_id: str):
        self.session_id = session_id
        self.current_question_id = current_question_id


def participant_ref_from_phone(from_number: str) -> str:
    """Normalize an E.164 caller number to phone:{12-char sha256} (matches discord hashing)."""
    digest = sha256(from_number.encode("utf-8")).hexdigest()[:12]
    return f"phone:{digest}"


# --------------------------------------------------------------------------- #
# TwiML rendering helpers
# --------------------------------------------------------------------------- #


def _twiml(*verbs: str) -> Response:
    body = '<?xml version="1.0" encoding="UTF-8"?><Response>' + "".join(verbs) + "</Response>"
    return Response(content=body, media_type="application/xml")


def _say(text: str, language: str) -> str:
    return f'<Say language="{xml_escape(language)}">{xml_escape(text)}</Say>'


def _play(url: str) -> str:
    return f"<Play>{xml_escape(url)}</Play>"


def _question_verb(text: str, tts: dict | None, settings: Settings) -> str:
    """Speak a question: <Play> the orchestrator wav when audio mode is on, else <Say>."""
    if settings.telephony_use_tts_audio and settings.public_base_url and tts:
        audio_path = tts.get("audio_path")
        if audio_path:
            basename = os.path.basename(audio_path)
            url = f"{settings.public_base_url.rstrip('/')}/media/{basename}"
            return _play(url)
    return _say(text, settings.language)


def _gather(settings: Settings) -> str:
    return (
        f'<Gather input="speech" language="{xml_escape(settings.language)}" '
        f'speechTimeout="auto" action="/voice/answer" method="POST"></Gather>'
    )


def create_app(settings: Settings | None = None, client: OrchestratorClient | None = None) -> FastAPI:
    resolved = settings or Settings()
    orchestrator = client or OrchestratorClient(
        resolved.orchestrator_base_url, timeout=resolved.orchestrator_timeout_sec
    )
    calls: dict[str, CallState] = {}
    app = FastAPI(title="ARS Telephony Gateway", version="0.1.0")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "telephony-gateway"}

    @app.post("/voice/incoming")
    async def voice_incoming(
        request: Request,
        CallSid: str = Form(default=""),
        From: str = Form(default=""),
    ) -> Response:
        """Twilio inbound webhook: start a session and speak question 1."""
        participant_ref = participant_ref_from_phone(From or CallSid or "anonymous")
        try:
            payload = await orchestrator.start_session(
                survey_id=resolved.default_survey_id,
                participant_ref=participant_ref,
                channel="phone",
            )
        except Exception:  # noqa: BLE001 - never leave the caller hanging on an error
            return _twiml(_say("설문 시스템에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.", resolved.language), "<Hangup/>")

        question = payload["current_question"]
        if CallSid:
            calls[CallSid] = CallState(payload["session_id"], question["question_id"])
        return _twiml(_question_verb(question["text"], payload.get("tts"), resolved), _gather(resolved))

    @app.post("/voice/answer")
    async def voice_answer(
        request: Request,
        CallSid: str = Form(default=""),
        SpeechResult: str = Form(default=""),
    ) -> Response:
        """Twilio Gather callback: submit the recognized transcript, speak the next question."""
        state = calls.get(CallSid)
        if state is None:
            # Unknown call (e.g. expired state) — restart cleanly.
            return _twiml(
                _say("진행 중인 설문을 찾을 수 없습니다. 다시 전화해 주세요.", resolved.language),
                "<Hangup/>",
            )

        transcript = (SpeechResult or "").strip()
        if not transcript:
            # Twilio heard nothing — re-prompt the same question instead of submitting empty.
            return _twiml(
                _say("응답을 듣지 못했습니다. 다시 말씀해 주세요.", resolved.language),
                _gather(resolved),
            )

        try:
            payload = await orchestrator.submit_answer(
                session_id=state.session_id,
                question_id=state.current_question_id,
                transcript=transcript,
            )
        except NoSpeechDetected:
            return _twiml(
                _say("응답을 인식하지 못했습니다. 다시 말씀해 주세요.", resolved.language),
                _gather(resolved),
            )
        except Exception:  # noqa: BLE001
            return _twiml(_say("응답 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", resolved.language), "<Hangup/>")

        if payload["status"] == "completed" or not payload.get("next_question"):
            calls.pop(CallSid, None)
            return _twiml(
                _say("응답해 주셔서 감사합니다. 설문이 완료되었습니다.", resolved.language),
                "<Hangup/>",
            )

        next_question = payload["next_question"]
        state.current_question_id = next_question["question_id"]
        return _twiml(
            _question_verb(next_question["text"], payload.get("tts"), resolved),
            _gather(resolved),
        )

    @app.get("/media/{filename}")
    async def media(filename: str) -> FileResponse:
        """Serve TTS wav files for <Play>, with path-traversal protection."""
        # Reject any path separators / parent refs; only a bare basename is allowed.
        if filename != os.path.basename(filename) or filename in (".", ".."):
            raise HTTPException(status_code=400, detail="invalid filename")
        base_dir = os.path.realpath(resolved.tts_dir)
        full_path = os.path.realpath(os.path.join(base_dir, filename))
        if not full_path.startswith(base_dir + os.sep):
            raise HTTPException(status_code=400, detail="invalid path")
        if not os.path.isfile(full_path):
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(full_path, media_type="audio/wav")

    return app


app = create_app()
