from __future__ import annotations

import httpx


class NoSpeechDetected(Exception):
    """Raised when the orchestrator reports no speech in a submitted answer (HTTP 422)."""


class OrchestratorClient:
    """Thin async HTTP client over the channel-agnostic AI Orchestrator.

    Adapted from services/discord-bot/app/orchestrator_client.py. The phone
    gateway only submits transcripts (Twilio runs the STT in Option A), so the
    audio-answer path is omitted here.
    """

    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.client = client
        # Answer submission runs LLM analysis (and, for audio channels, STT) on
        # the orchestrator, which can exceed 10s on CPU / cold model loads. Keep
        # this at or above the orchestrator's own LLM timeout to avoid aborts.
        self.timeout = timeout

    async def start_session(self, *, survey_id: str, participant_ref: str, channel: str = "phone") -> dict:
        return await self._post(
            "/sessions",
            {
                "survey_id": survey_id,
                "participant_ref": participant_ref,
                "channel": channel,
            },
        )

    async def submit_answer(self, *, session_id: str, question_id: str, transcript: str) -> dict:
        return await self._post(
            f"/sessions/{session_id}/answers",
            {
                "question_id": question_id,
                "transcript": transcript,
                "source": "phone",
            },
        )

    async def get_summary(self, *, session_id: str) -> dict:
        return await self._get(f"/sessions/{session_id}/summary")

    async def _post(self, path: str, payload: dict) -> dict:
        if self.client:
            response = await self.client.post(f"{self.base_url}{path}", json=payload)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
        if response.status_code == 422:
            raise NoSpeechDetected()
        response.raise_for_status()
        return response.json()

    async def _get(self, path: str) -> dict:
        if self.client:
            response = await self.client.get(f"{self.base_url}{path}")
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}{path}")
        response.raise_for_status()
        return response.json()
