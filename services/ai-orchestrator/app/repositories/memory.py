from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models import AgentResult, StoredResponse, StoredSession
from app.repositories.base import Repository


class MemoryRepository(Repository):
    def __init__(self) -> None:
        self.sessions: dict[str, StoredSession] = {}
        self.responses: list[StoredResponse] = []
        self.agent_logs: list[dict[str, Any]] = []

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
