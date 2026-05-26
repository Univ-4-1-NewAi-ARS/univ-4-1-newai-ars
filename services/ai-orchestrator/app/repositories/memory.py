from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models import AgentResult, StoredAudioRecord, StoredResponse, StoredSession
from app.repositories.base import Repository


class MemoryRepository(Repository):
    def __init__(self) -> None:
        self.sessions: dict[str, StoredSession] = {}
        self.responses: list[StoredResponse] = []
        self.audio_records: list[StoredAudioRecord] = []
        self.agent_logs: list[dict[str, Any]] = []
        self.audit_events: list[dict[str, Any]] = []

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ensure_schema(self) -> None:
        return None

    async def create_session(self, *, survey_id: str, participant_ref: str, channel: str, current_question_id: str) -> StoredSession:
        session = StoredSession(
            id=str(uuid4()),
            survey_id=survey_id,
            participant_ref=participant_ref,
            channel=channel,
            status="in_progress",
            current_question_id=current_question_id,
            started_at=datetime.now(timezone.utc),
            metadata={},
        )
        self.sessions[session.id] = session
        return session

    async def get_session(self, session_id: str) -> StoredSession | None:
        return self.sessions.get(session_id)

    async def update_session(
        self,
        *,
        session_id: str,
        status: str,
        current_question_id: str | None,
        retry_count: int,
        completed: bool,
    ) -> StoredSession:
        session = self.sessions[session_id]
        updated = session.model_copy(
            update={
                "status": status,
                "current_question_id": current_question_id,
                "retry_count": retry_count,
                "completed_at": datetime.now(timezone.utc) if completed else session.completed_at,
            }
        )
        self.sessions[session_id] = updated
        return updated

    async def add_response(self, *, session_id: str, result: AgentResult) -> StoredResponse:
        response = StoredResponse(
            id=str(uuid4()),
            session_id=session_id,
            question_id=result.question_id,
            agent_result=result,
            created_at=datetime.now(timezone.utc),
        )
        self.responses.append(response)
        return response

    async def list_responses(self, session_id: str) -> list[StoredResponse]:
        return [response for response in self.responses if response.session_id == session_id]

    async def list_responses_for_survey(self, survey_id: str) -> list[StoredResponse]:
        session_ids = {session.id for session in self.sessions.values() if session.survey_id == survey_id}
        return [response for response in self.responses if response.session_id in session_ids]

    async def count_sessions_for_survey(self, survey_id: str) -> int:
        return sum(1 for session in self.sessions.values() if session.survey_id == survey_id)

    async def add_audio_record(
        self,
        *,
        session_id: str,
        question_id: str,
        record_type: str,
        file_path: str,
        duration_sec: float | None,
        provider: str,
        retention_until: datetime | None,
    ) -> StoredAudioRecord:
        record = StoredAudioRecord(
            id=str(uuid4()),
            session_id=session_id,
            question_id=question_id,
            record_type=record_type,
            file_path=file_path,
            duration_sec=duration_sec,
            provider=provider,
            retention_until=retention_until,
            created_at=datetime.now(timezone.utc),
        )
        self.audio_records.append(record)
        return record

    async def list_expired_audio_records(self, *, now: datetime, limit: int = 100) -> list[StoredAudioRecord]:
        expired = [record for record in self.audio_records if record.retention_until and record.retention_until <= now]
        return expired[:limit]

    async def delete_audio_record(self, record_id: str) -> None:
        self.audio_records = [record for record in self.audio_records if record.id != record_id]

    async def add_agent_log(
        self,
        *,
        session_id: str,
        question_id: str,
        provider: str,
        parsed_result: dict[str, Any],
        retry_count: int = 0,
        fallback_used: bool = False,
        error_message: str | None = None,
    ) -> None:
        self.agent_logs.append(
            {
                "session_id": session_id,
                "question_id": question_id,
                "provider": provider,
                "parsed_result": parsed_result,
                "retry_count": retry_count,
                "fallback_used": fallback_used,
                "error_message": error_message,
            }
        )

    async def add_audit_event(
        self,
        *,
        event_type: str,
        severity: str,
        session_id: str | None,
        actor_ref: str | None,
        details: dict[str, Any],
    ) -> None:
        self.audit_events.append(
            {
                "event_type": event_type,
                "severity": severity,
                "session_id": session_id,
                "actor_ref": actor_ref,
                "details": details,
                "created_at": datetime.now(timezone.utc),
            }
        )
