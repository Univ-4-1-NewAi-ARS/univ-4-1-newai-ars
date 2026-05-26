from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import asyncpg

from app.models import AgentResult, StoredResponse, StoredSession
from app.repositories.base import Repository


class PostgresRepository(Repository):
    def __init__(self, dsn: str, schema_path: Path):
        self.dsn = dsn
        self.schema_path = schema_path
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def ensure_schema(self) -> None:
        if not self.pool:
            raise RuntimeError("Postgres pool is not connected")
        sql = self.schema_path.read_text(encoding="utf-8")
        async with self.pool.acquire() as connection:
            await connection.execute(sql)

    async def create_session(self, *, survey_id: str, participant_ref: str, channel: str, current_question_id: str) -> StoredSession:
        if not self.pool:
            raise RuntimeError("Postgres pool is not connected")
        session_id = str(uuid4())
        row = await self.pool.fetchrow(
            """
            INSERT INTO survey_sessions (id, survey_id, participant_ref, channel, status, current_question_id, retry_count, metadata)
            VALUES ($1, $2, $3, $4, 'in_progress', $5, 0, '{}'::jsonb)
            RETURNING *
            """,
            session_id,
            survey_id,
            participant_ref,
            channel,
            current_question_id,
        )
        return self._session_from_row(row)

    async def get_session(self, session_id: str) -> StoredSession | None:
        if not self.pool:
            raise RuntimeError("Postgres pool is not connected")
        row = await self.pool.fetchrow("SELECT * FROM survey_sessions WHERE id = $1", session_id)
        return self._session_from_row(row) if row else None

    async def update_session(
        self,
        *,
        session_id: str,
        status: str,
        current_question_id: str | None,
        retry_count: int,
        completed: bool,
    ) -> StoredSession:
        if not self.pool:
            raise RuntimeError("Postgres pool is not connected")
        completed_at = datetime.now(timezone.utc) if completed else None
        row = await self.pool.fetchrow(
            """
            UPDATE survey_sessions
            SET status = $2,
                current_question_id = $3,
                retry_count = $4,
                completed_at = COALESCE($5, completed_at)
            WHERE id = $1
            RETURNING *
            """,
            session_id,
            status,
            current_question_id,
            retry_count,
            completed_at,
        )
        return self._session_from_row(row)

    async def add_response(self, *, session_id: str, result: AgentResult) -> StoredResponse:
        if not self.pool:
            raise RuntimeError("Postgres pool is not connected")
        response_id = str(uuid4())
        payload = result.model_dump(mode="json")
        row = await self.pool.fetchrow(
            """
            INSERT INTO survey_responses (
                id, session_id, question_id, raw_transcript, cleaned_text, answer_type,
                selected_option, confidence, sentiment, keywords, needs_retry,
                review_required, reason, agent_result
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12, $13, $14::jsonb)
            RETURNING id, session_id, question_id, agent_result, created_at
            """,
            response_id,
            session_id,
            result.question_id,
            result.raw_transcript,
            result.cleaned_text,
            result.answer_type,
            result.selected_option,
            result.confidence,
            result.sentiment,
            json.dumps(result.keywords, ensure_ascii=False),
            result.needs_retry,
            result.review_required,
            result.reason,
            json.dumps(payload, ensure_ascii=False),
        )
        return self._response_from_row(row)

    async def list_responses(self, session_id: str) -> list[StoredResponse]:
        if not self.pool:
            raise RuntimeError("Postgres pool is not connected")
        rows = await self.pool.fetch(
            "SELECT id, session_id, question_id, agent_result, created_at FROM survey_responses WHERE session_id = $1 ORDER BY created_at ASC",
            session_id,
        )
        return [self._response_from_row(row) for row in rows]

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
        if not self.pool:
            raise RuntimeError("Postgres pool is not connected")
        await self.pool.execute(
            """
            INSERT INTO agent_logs (
                id, session_id, question_id, provider, prompt_hash, request_schema,
                raw_response, parsed_result, retry_count, fallback_used, error_message
            )
            VALUES ($1, $2, $3, $4, NULL, '{}'::jsonb, NULL, $5::jsonb, $6, $7, $8)
            """,
            str(uuid4()),
            session_id,
            question_id,
            provider,
            json.dumps(parsed_result, ensure_ascii=False),
            retry_count,
            fallback_used,
            error_message,
        )

    def _session_from_row(self, row: asyncpg.Record) -> StoredSession:
        return StoredSession(
            id=str(row["id"]),
            survey_id=row["survey_id"],
            participant_ref=row["participant_ref"],
            channel=row["channel"],
            status=row["status"],
            current_question_id=row["current_question_id"],
            retry_count=row["retry_count"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            metadata=dict(row["metadata"] or {}),
        )

    def _response_from_row(self, row: asyncpg.Record) -> StoredResponse:
        payload = row["agent_result"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return StoredResponse(
            id=str(row["id"]),
            session_id=str(row["session_id"]),
            question_id=row["question_id"],
            agent_result=AgentResult.model_validate(payload),
            created_at=row["created_at"],
        )
