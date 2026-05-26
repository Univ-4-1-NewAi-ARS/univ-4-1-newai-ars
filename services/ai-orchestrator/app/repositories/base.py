from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.models import AgentResult, StoredAudioRecord, StoredResponse, StoredSession


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
        raise NotImplementedError

    @abstractmethod
    async def list_expired_audio_records(self, *, now: datetime, limit: int = 100) -> list[StoredAudioRecord]:
        raise NotImplementedError

    @abstractmethod
    async def delete_audio_record(self, record_id: str) -> None:
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

    @abstractmethod
    async def add_audit_event(
        self,
        *,
        event_type: str,
        severity: str,
        session_id: str | None,
        actor_ref: str | None,
        details: dict[str, Any],
    ) -> None:
        raise NotImplementedError
