import pytest
from fastapi import HTTPException

from app.core.settings import Settings
from app.models import AnswerSubmitRequest, SessionCreateRequest, TranscriptionResult
from app.providers.mock import MockTTSProvider
from app.repositories.memory import MemoryRepository
from app.services.orchestrator import OrchestratorService
from app.survey_loader import SurveyLoader
from conftest import SURVEY_DIR


class _NoSpeechSTT:
    """STT that ran fine but heard no speech (empty transcript)."""

    async def transcribe(self, audio_path: str, language: str) -> TranscriptionResult:
        return TranscriptionResult(text="", language=language, confidence=0.0, duration_sec=0.1, provider="local_whisper")


def _service(repo: MemoryRepository) -> OrchestratorService:
    settings = Settings(repository_provider="memory", survey_dir=SURVEY_DIR, save_raw_audio=False)
    return OrchestratorService(
        settings=settings,
        repository=repo,
        survey_loader=SurveyLoader(settings.survey_dir),
        answer_analyzer=object(),  # not reached on the no-speech path
        stt_provider=_NoSpeechSTT(),
        tts_provider=MockTTSProvider(),
    )


async def test_no_speech_audio_returns_422_and_fabricates_nothing() -> None:
    repo = MemoryRepository()
    service = _service(repo)
    created = await service.start_session(
        SessionCreateRequest(survey_id="campus_opinion_survey", participant_ref="discord:x", channel="discord_voice")
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.submit_answer(
            created.session_id,
            AnswerSubmitRequest(question_id="q1", audio_path="/data/audio/x.wav", source="discord_voice"),
        )

    assert exc_info.value.status_code == 422
    # No fabricated answer stored, and the session stays on the same question.
    assert await repo.list_responses(created.session_id) == []
    # The failure is recorded honestly for the dashboard / logs.
    assert any(event["event_type"] == "answer_no_speech" for event in repo.audit_events)
