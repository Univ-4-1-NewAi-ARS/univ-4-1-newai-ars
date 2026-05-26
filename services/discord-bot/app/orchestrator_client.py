from __future__ import annotations

import httpx


class OrchestratorClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.client = client

    async def start_session(self, *, survey_id: str, participant_ref: str, channel: str = "discord_text") -> dict:
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
                "source": "discord_text",
            },
        )

    async def get_summary(self, *, session_id: str) -> dict:
        return await self._get(f"/sessions/{session_id}/summary")

    async def _post(self, path: str, payload: dict) -> dict:
        if self.client:
            response = await self.client.post(f"{self.base_url}{path}", json=payload)
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
        response.raise_for_status()
        return response.json()

    async def _get(self, path: str) -> dict:
        if self.client:
            response = await self.client.get(f"{self.base_url}{path}")
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}{path}")
        response.raise_for_status()
        return response.json()
