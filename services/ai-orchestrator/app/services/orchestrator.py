from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from app.agents.answer_analyzer import AnswerAnalyzer
from app.core.settings import Settings
from app.models import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    QuestionPayload,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionSummaryResponse,
    SurveyStatsResponse,
    ReportExportResponse,
)
from app.providers.mock import MockSTTProvider, MockTTSProvider
from app.repositories.base import Repository
from app.services.report_exporter import MarkdownReportExporter
from app.survey_loader import SurveyLoader, SurveyNotFoundError


class OrchestratorService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: Repository,
        survey_loader: SurveyLoader,
        answer_analyzer: AnswerAnalyzer,
        stt_provider: MockSTTProvider,
        tts_provider: MockTTSProvider,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.survey_loader = survey_loader
        self.answer_analyzer = answer_analyzer
        self.stt_provider = stt_provider
        self.tts_provider = tts_provider
        self.report_exporter = MarkdownReportExporter(settings.report_dir)

    async def start_session(self, request: SessionCreateRequest) -> SessionCreateResponse:
        survey = self._load_survey_or_404(request.survey_id)
        first_question = survey.first_question()
        session = await self.repository.create_session(
            survey_id=survey.survey_id,
            participant_ref=request.participant_ref,
            channel=request.channel,
            current_question_id=first_question.question_id,
        )
        tts = await self.tts_provider.synthesize(
            first_question.text,
            self.settings.tts_voice,
            survey.survey_id,
            first_question.question_id,
        )
        return SessionCreateResponse(
            session_id=session.id,
            survey_id=session.survey_id,
            status=session.status,
            current_question=QuestionPayload.from_question(first_question),
            tts=tts,
        )

    async def submit_answer(self, session_id: str, request: AnswerSubmitRequest) -> AnswerSubmitResponse:
        session = await self.repository.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session.status != "in_progress":
            raise HTTPException(status_code=409, detail=f"Session is not accepting answers: {session.status}")
        if session.current_question_id != request.question_id:
            raise HTTPException(status_code=400, detail="Answer question_id does not match current session question")

        survey = self._load_survey_or_404(session.survey_id)
        question = survey.get_question(request.question_id)
        transcript = request.transcript
        if not transcript and request.audio_path:
            transcription = await self.stt_provider.transcribe(request.audio_path, self.settings.stt_language)
            transcript = transcription.text
        if not transcript:
            raise HTTPException(status_code=400, detail="Either transcript or audio_path is required")

        agent_run = await self.answer_analyzer.analyze_answer(question, transcript)
        agent_result = agent_run.result
        await self.repository.add_response(session_id=session.id, result=agent_result)
        await self.repository.add_agent_log(
            session_id=session.id,
            question_id=question.question_id,
            provider=agent_run.provider,
            parsed_result=agent_result.model_dump(mode="json"),
            retry_count=agent_run.retry_count,
            fallback_used=agent_run.fallback_used,
            error_message=agent_run.error_message,
        )

        if agent_result.needs_retry and session.retry_count < self.settings.max_retry_per_question:
            updated = await self.repository.update_session(
                session_id=session.id,
                status="in_progress",
                current_question_id=question.question_id,
                retry_count=session.retry_count + 1,
                completed=False,
            )
            tts = await self.tts_provider.synthesize(question.text, self.settings.tts_voice, survey.survey_id, question.question_id)
            return AnswerSubmitResponse(
                session_id=updated.id,
                status=updated.status,
                agent_result=agent_result,
                next_question=QuestionPayload.from_question(question),
                tts=tts,
            )

        next_question = survey.next_question_after(question.question_id)
        if next_question:
            updated = await self.repository.update_session(
                session_id=session.id,
                status="in_progress",
                current_question_id=next_question.question_id,
                retry_count=0,
                completed=False,
            )
            tts = await self.tts_provider.synthesize(next_question.text, self.settings.tts_voice, survey.survey_id, next_question.question_id)
            return AnswerSubmitResponse(
                session_id=updated.id,
                status=updated.status,
                agent_result=agent_result,
                next_question=QuestionPayload.from_question(next_question),
                tts=tts,
            )

        updated = await self.repository.update_session(
            session_id=session.id,
            status="completed",
            current_question_id=None,
            retry_count=0,
            completed=True,
        )
        return AnswerSubmitResponse(
            session_id=updated.id,
            status=updated.status,
            agent_result=agent_result,
            next_question=None,
            tts=None,
        )

    async def get_summary(self, session_id: str) -> SessionSummaryResponse:
        session = await self.repository.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        responses = await self.repository.list_responses(session_id)
        return SessionSummaryResponse(
            session_id=session.id,
            survey_id=session.survey_id,
            status=session.status,
            current_question_id=session.current_question_id,
            response_count=len(responses),
            responses=[response.agent_result for response in responses],
        )

    async def get_survey_stats(self, survey_id: str) -> SurveyStatsResponse:
        self._load_survey_or_404(survey_id)
        responses = await self.repository.list_responses_for_survey(survey_id)
        session_count = await self.repository.count_sessions_for_survey(survey_id)
        option_counts: dict[str, dict[str, int]] = {}
        sentiment_counts: dict[str, int] = {}

        for response in responses:
            result = response.agent_result
            sentiment_counts[result.sentiment] = sentiment_counts.get(result.sentiment, 0) + 1
            if result.selected_option:
                question_counts = option_counts.setdefault(result.question_id, {})
                question_counts[result.selected_option] = question_counts.get(result.selected_option, 0) + 1

        return SurveyStatsResponse(
            survey_id=survey_id,
            session_count=session_count,
            response_count=len(responses),
            option_counts=option_counts,
            sentiment_counts=sentiment_counts,
            generated_at=datetime.now(timezone.utc),
        )

    async def export_survey_report(self, survey_id: str) -> ReportExportResponse:
        stats = await self.get_survey_stats(survey_id)
        report_path = self.report_exporter.export(stats)
        return ReportExportResponse(survey_id=survey_id, report_path=str(report_path), generated_at=stats.generated_at)

    def _load_survey_or_404(self, survey_id: str):
        try:
            return self.survey_loader.load(survey_id)
        except SurveyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
