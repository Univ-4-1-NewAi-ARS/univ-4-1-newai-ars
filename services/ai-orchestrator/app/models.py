from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SessionStatus = Literal["created", "in_progress", "completed", "abandoned", "failed"]
SurveyChannel = Literal["discord_text", "discord_voice", "phone", "mock"]


class AnswerOption(BaseModel):
    id: str
    label: str


class SurveyQuestion(BaseModel):
    question_id: str
    text: str
    answer_type: Literal["single_choice", "free_text"]
    options: list[AnswerOption] = Field(default_factory=list)


class SurveyDefinition(BaseModel):
    survey_id: str
    title: str
    language: str = "ko"
    version: str
    questions: list[SurveyQuestion]

    def first_question(self) -> SurveyQuestion:
        return self.questions[0]

    def get_question(self, question_id: str) -> SurveyQuestion:
        for question in self.questions:
            if question.question_id == question_id:
                return question
        raise KeyError(f"Unknown question_id: {question_id}")

    def next_question_after(self, question_id: str) -> SurveyQuestion | None:
        for index, question in enumerate(self.questions):
            if question.question_id == question_id:
                next_index = index + 1
                if next_index >= len(self.questions):
                    return None
                return self.questions[next_index]
        raise KeyError(f"Unknown question_id: {question_id}")


class QuestionPayload(BaseModel):
    question_id: str
    text: str
    answer_type: str
    options: list[AnswerOption] = Field(default_factory=list)

    @classmethod
    def from_question(cls, question: SurveyQuestion) -> "QuestionPayload":
        return cls(
            question_id=question.question_id,
            text=question.text,
            answer_type=question.answer_type,
            options=question.options,
        )


class TTSResult(BaseModel):
    audio_path: str
    duration_sec: float
    provider: str
    cached: bool = True
    fallback_used: bool = False


class TranscriptionResult(BaseModel):
    text: str
    language: str
    confidence: float
    duration_sec: float | None = None
    provider: str
    fallback_used: bool = False


class AgentResult(BaseModel):
    question_id: str
    raw_transcript: str
    cleaned_text: str
    answer_type: str
    selected_option: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    sentiment: Literal["positive", "neutral", "negative", "unknown"]
    keywords: list[str] = Field(default_factory=list)
    needs_retry: bool
    review_required: bool
    reason: str


class SessionCreateRequest(BaseModel):
    survey_id: str
    participant_ref: str
    channel: SurveyChannel = "mock"


class SessionCreateResponse(BaseModel):
    session_id: str
    survey_id: str
    status: SessionStatus
    current_question: QuestionPayload
    tts: TTSResult | None = None


class AnswerSubmitRequest(BaseModel):
    question_id: str
    transcript: str | None = None
    audio_path: str | None = None
    source: SurveyChannel = "mock"


class AnswerSubmitResponse(BaseModel):
    session_id: str
    status: SessionStatus
    agent_result: AgentResult
    next_question: QuestionPayload | None = None
    tts: TTSResult | None = None


class SessionSummaryResponse(BaseModel):
    session_id: str
    survey_id: str
    status: SessionStatus
    current_question_id: str | None
    response_count: int
    responses: list[AgentResult]


class SurveyStatsResponse(BaseModel):
    survey_id: str
    session_count: int
    response_count: int
    option_counts: dict[str, dict[str, int]]
    sentiment_counts: dict[str, int]
    generated_at: datetime


class OpinionItem(BaseModel):
    text: str
    sentiment: str
    keywords: list[str] = Field(default_factory=list)
    confidence: float | None = None


class QuestionInsight(BaseModel):
    question_id: str
    text: str
    answer_type: str
    response_count: int
    sentiment_counts: dict[str, int] = Field(default_factory=dict)
    option_counts: dict[str, int] = Field(default_factory=dict)
    keyword_counts: dict[str, int] = Field(default_factory=dict)
    opinions: list[OpinionItem] = Field(default_factory=list)


class SurveyInsightsResponse(BaseModel):
    survey_id: str
    response_count: int
    sentiment_counts: dict[str, int] = Field(default_factory=dict)
    keyword_counts: dict[str, int] = Field(default_factory=dict)
    questions: list[QuestionInsight] = Field(default_factory=list)
    generated_at: datetime


class ReportExportResponse(BaseModel):
    survey_id: str
    report_path: str
    generated_at: datetime


class RetentionCleanupResponse(BaseModel):
    expired_records: int
    deleted_files: int
    missing_files: int
    skipped_files: int
    dry_run: bool
    record_ids: list[str] = Field(default_factory=list)


class ProviderRuntimeResponse(BaseModel):
    llm: dict[str, Any]
    stt: dict[str, Any]
    tts: dict[str, Any]


class StoredSession(BaseModel):
    id: str
    survey_id: str
    participant_ref: str
    channel: str
    status: SessionStatus
    current_question_id: str | None
    retry_count: int = 0
    started_at: datetime
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoredResponse(BaseModel):
    id: str
    session_id: str
    question_id: str
    agent_result: AgentResult
    created_at: datetime


class StoredAudioRecord(BaseModel):
    id: str
    session_id: str
    question_id: str | None
    record_type: str
    file_path: str
    duration_sec: float | None = None
    provider: str
    retention_until: datetime | None = None
    created_at: datetime


class StoredAuditEvent(BaseModel):
    id: str | None = None
    event_type: str
    severity: str
    session_id: str | None = None
    actor_ref: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AuditEventsResponse(BaseModel):
    count: int
    events: list[StoredAuditEvent] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    service: str
    repository: str

    model_config = ConfigDict(json_schema_extra={"example": {"status": "ok", "service": "ai-orchestrator", "repository": "postgres"}})
