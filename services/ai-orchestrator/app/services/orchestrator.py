from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from app.agents.answer_analyzer import AnswerAnalyzer
from app.core.privacy import (
    TRANSCRIPT_REDACTED_TEXT,
    is_path_inside,
    mask_sensitive_text,
    normalize_participant_ref,
    retention_deadline,
)
from app.core.settings import Settings
from app.models import (
    AgentResult,
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    AuditEventsResponse,
    OpinionItem,
    QuestionInsight,
    QuestionPayload,
    ReportExportResponse,
    RetentionCleanupResponse,
    ProviderRuntimeResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionSummaryResponse,
    SurveyInsightsResponse,
    SurveyStatsResponse,
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
        participant_ref = normalize_participant_ref(request.participant_ref, self.settings.participant_hash_salt)
        session = await self.repository.create_session(
            survey_id=survey.survey_id,
            participant_ref=participant_ref,
            channel=request.channel,
            current_question_id=first_question.question_id,
        )
        await self.repository.add_audit_event(
            event_type="session_started",
            severity="info",
            session_id=session.id,
            actor_ref=participant_ref,
            details={"survey_id": survey.survey_id, "channel": request.channel},
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
        transcription = None
        if not transcript and request.audio_path:
            transcription = await self.stt_provider.transcribe(request.audio_path, self.settings.stt_language)
            transcript = transcription.text
            await self._record_input_audio(session.id, question.question_id, request.audio_path, transcription.provider, transcription.duration_sec)
            if not (transcript and transcript.strip()):
                # STT heard no speech in the audio. Do not fabricate or store an
                # answer; signal the caller to re-ask. Keeps survey data honest.
                await self.repository.add_audit_event(
                    event_type="answer_no_speech",
                    severity="warning",
                    session_id=session.id,
                    actor_ref=session.participant_ref,
                    details={"question_id": question.question_id, "provider": transcription.provider},
                )
                raise HTTPException(status_code=422, detail="No speech detected in audio")
        if not transcript:
            raise HTTPException(status_code=400, detail="Either transcript or audio_path is required")

        agent_run = await self.answer_analyzer.analyze_answer(question, transcript)
        agent_result = agent_run.result
        stored_result = self._result_for_storage(agent_result)
        await self.repository.add_response(session_id=session.id, result=stored_result)
        await self.repository.add_agent_log(
            session_id=session.id,
            question_id=question.question_id,
            provider=agent_run.provider,
            parsed_result=stored_result.model_dump(mode="json"),
            retry_count=agent_run.retry_count,
            fallback_used=agent_run.fallback_used,
            error_message=mask_sensitive_text(agent_run.error_message, extra_secrets=[self.settings.openai_api_key]),
        )
        await self.repository.add_audit_event(
            event_type="answer_processed",
            severity="info",
            session_id=session.id,
            actor_ref=session.participant_ref,
            details={
                "question_id": question.question_id,
                "source": request.source,
                "fallback_used": agent_run.fallback_used,
                "retry_count": agent_run.retry_count,
                "audio_input": request.audio_path is not None,
                "transcript_saved": self.settings.save_transcript,
            },
        )

        if self._should_retry(question, agent_result) and session.retry_count < self.settings.max_retry_per_question:
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
                agent_result=stored_result,
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
                agent_result=stored_result,
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
            agent_result=stored_result,
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

    async def get_survey_insights(self, survey_id: str, *, max_opinions: int = 50) -> SurveyInsightsResponse:
        survey = self._load_survey_or_404(survey_id)
        responses = await self.repository.list_responses_for_survey(survey_id)

        grouped: dict[str, list] = {}
        for response in responses:
            grouped.setdefault(response.agent_result.question_id, []).append(response)

        overall_sentiment: dict[str, int] = {}
        overall_keywords: dict[str, int] = {}
        questions: list[QuestionInsight] = []

        for question in survey.questions:
            items = grouped.get(question.question_id, [])
            option_label = {option.id: option.label for option in question.options}
            sentiment_counts: dict[str, int] = {}
            keyword_counts: dict[str, int] = {}
            option_counts: dict[str, int] = {}
            opinions: list[OpinionItem] = []

            for response in items:
                result = response.agent_result
                sentiment_counts[result.sentiment] = sentiment_counts.get(result.sentiment, 0) + 1
                overall_sentiment[result.sentiment] = overall_sentiment.get(result.sentiment, 0) + 1
                for keyword in result.keywords:
                    keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
                    overall_keywords[keyword] = overall_keywords.get(keyword, 0) + 1
                if question.answer_type == "single_choice" and result.selected_option:
                    label = option_label.get(result.selected_option, result.selected_option)
                    option_counts[label] = option_counts.get(label, 0) + 1
                if question.answer_type == "free_text":
                    text = result.cleaned_text
                    if text and text != TRANSCRIPT_REDACTED_TEXT:
                        opinions.append(
                            OpinionItem(
                                text=text,
                                sentiment=result.sentiment,
                                keywords=result.keywords,
                                confidence=result.confidence,
                            )
                        )

            questions.append(
                QuestionInsight(
                    question_id=question.question_id,
                    text=question.text,
                    answer_type=question.answer_type,
                    response_count=len(items),
                    sentiment_counts=sentiment_counts,
                    option_counts=option_counts,
                    keyword_counts=dict(sorted(keyword_counts.items(), key=lambda kv: kv[1], reverse=True)),
                    opinions=list(reversed(opinions))[:max_opinions],
                )
            )

        top_keywords = dict(sorted(overall_keywords.items(), key=lambda kv: kv[1], reverse=True)[:20])
        return SurveyInsightsResponse(
            survey_id=survey_id,
            response_count=len(responses),
            sentiment_counts=overall_sentiment,
            keyword_counts=top_keywords,
            questions=questions,
            generated_at=datetime.now(timezone.utc),
        )

    async def export_survey_report(self, survey_id: str) -> ReportExportResponse:
        stats = await self.get_survey_stats(survey_id)
        report_path = self.report_exporter.export(stats)
        return ReportExportResponse(survey_id=survey_id, report_path=str(report_path), generated_at=stats.generated_at)

    async def get_provider_runtime(self) -> ProviderRuntimeResponse:
        return ProviderRuntimeResponse(
            llm={
                "provider": self.settings.llm_provider,
                "base_url": self.settings.llm_base_url,
                "model": self.settings.llm_model,
                "api_fallback_enabled": self.settings.llm_use_api_fallback,
                "mock_fallback_enabled": self.settings.llm_use_mock_fallback,
                "timeout_sec": self.settings.llm_timeout_sec,
                "status": "configured",
            },
            stt={
                "provider": self.settings.stt_provider,
                "base_url": self.settings.stt_base_url,
                "model": self.settings.stt_model,
                "language": self.settings.stt_language,
                "mock_fallback_enabled": self.settings.stt_use_mock_fallback,
                "status": "configured",
            },
            tts={
                "provider": self.settings.tts_provider,
                "base_url": self.settings.tts_base_url,
                "voice": self.settings.tts_voice,
                "language": self.settings.tts_language,
                "fallback_provider": self.settings.tts_fallback_provider,
                "cached_fallback_enabled": self.settings.tts_use_cached_fallback,
                "cache_enabled": self.settings.tts_cache_enabled,
                "status": "configured",
            },
        )

    async def list_audit_events(self, *, limit: int = 50) -> AuditEventsResponse:
        limit = max(1, min(limit, 200))
        events = await self.repository.list_audit_events(limit=limit)
        return AuditEventsResponse(count=len(events), events=events)

    async def cleanup_expired_audio(self, *, dry_run: bool = True) -> RetentionCleanupResponse:
        records = await self.repository.list_expired_audio_records(now=datetime.now(timezone.utc))
        record_ids = [record.id for record in records]
        deleted_files = 0
        missing_files = 0
        skipped_files = 0

        if not dry_run:
            for record in records:
                if not is_path_inside(record.file_path, self.settings.audio_dir):
                    skipped_files += 1
                    continue

                path = Path(record.file_path)
                if path.exists():
                    path.unlink()
                    deleted_files += 1
                else:
                    missing_files += 1
                await self.repository.delete_audio_record(record.id)

        await self.repository.add_audit_event(
            event_type="raw_audio_cleanup",
            severity="info",
            session_id=None,
            actor_ref=None,
            details={
                "dry_run": dry_run,
                "expired_records": len(records),
                "deleted_files": deleted_files,
                "missing_files": missing_files,
                "skipped_files": skipped_files,
            },
        )
        return RetentionCleanupResponse(
            expired_records=len(records),
            deleted_files=deleted_files,
            missing_files=missing_files,
            skipped_files=skipped_files,
            dry_run=dry_run,
            record_ids=record_ids,
        )

    def _should_retry(self, question, agent_result: AgentResult) -> bool:
        if not agent_result.needs_retry:
            return False
        # Free-text questions accept any captured opinion; a small local model
        # flagging needs_retry on a valid answer must not loop the same question.
        if question.answer_type == "free_text" and not self.settings.free_text_retry_enabled:
            return False
        return True

    def _load_survey_or_404(self, survey_id: str):
        try:
            return self.survey_loader.load(survey_id)
        except SurveyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def _record_input_audio(
        self,
        session_id: str,
        question_id: str,
        audio_path: str,
        provider: str,
        duration_sec: float | None,
    ) -> None:
        if not self.settings.save_raw_audio:
            await self.repository.add_audit_event(
                event_type="raw_audio_discarded",
                severity="info",
                session_id=session_id,
                actor_ref=None,
                details={"question_id": question_id, "provider": provider},
            )
            return

        await self.repository.add_audio_record(
            session_id=session_id,
            question_id=question_id,
            record_type="input_audio",
            file_path=audio_path,
            duration_sec=duration_sec,
            provider=provider,
            retention_until=retention_deadline(self.settings.raw_audio_retention_days),
        )

    def _result_for_storage(self, result: AgentResult) -> AgentResult:
        if self.settings.save_transcript:
            return result
        return result.model_copy(
            update={
                "raw_transcript": TRANSCRIPT_REDACTED_TEXT,
                "cleaned_text": TRANSCRIPT_REDACTED_TEXT,
                "keywords": [],
            }
        )
