from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models import AgentResult, StoredResponse, StoredSession


class Repository(ABC):
    @abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def ensure_schema(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def create_session(self, *, survey_id: str, participant_ref: str, channel: str, current_question_id: str) -> StoredSession:
        raise NotImplementedError

    @abstractmethod
    async def get_session(self, session_id: str) -> StoredSession | None:
        raise NotImplementedError

    @abstractmethod
    async def update_session(
        self,
        *,
        session_id: str,
        status: str,
        current_question_id: str | None,
        retry_count: int,
        completed: bool,
    ) -> StoredSession:
        raise NotImplementedError

    @abstractmethod
    async def add_response(self, *, session_id: str, result: AgentResult) -> StoredResponse:
        raise NotImplementedError

    @abstractmethod
    async def list_responses(self, session_id: str) -> list[StoredResponse]:
        raise NotImplementedError

    @abstractmethod
    async def list_responses_for_survey(self, survey_id: str) -> list[StoredResponse]:
        raise NotImplementedError

    @abstractmethod
    async def count_sessions_for_survey(self, survey_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError
