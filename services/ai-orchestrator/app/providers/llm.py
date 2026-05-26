from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.settings import Settings
from app.models import AgentResult, SurveyQuestion


class ProviderUnavailable(RuntimeError):
    pass


class LLMProvider(ABC):
    provider_name: str

    @abstractmethod
    async def generate_json(self, *, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    provider_name = "mock"

    async def generate_json(self, *, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        payload = json.loads(prompt)
        question = SurveyQuestion.model_validate(payload["question"])
        transcript = payload["transcript"]
        return (await self.analyze_answer(question, transcript)).model_dump(mode="json")

    async def analyze_answer(self, question: SurveyQuestion, transcript: str) -> AgentResult:
        cleaned = " ".join(transcript.strip().split())
        if question.answer_type == "single_choice":
            selected = self._match_option(question, cleaned)
            if selected:
                return AgentResult(
                    question_id=question.question_id,
                    raw_transcript=transcript,
                    cleaned_text=cleaned,
                    answer_type=question.answer_type,
                    selected_option=selected,
                    confidence=0.86,
                    sentiment=self._sentiment(cleaned),
                    keywords=self._keywords(cleaned),
                    needs_retry=False,
                    review_required=False,
                    reason=f"Transcript matched option {selected}.",
                )
            return AgentResult(
                question_id=question.question_id,
                raw_transcript=transcript,
                cleaned_text=cleaned,
                answer_type=question.answer_type,
                selected_option=None,
                confidence=0.28,
                sentiment=self._sentiment(cleaned),
                keywords=self._keywords(cleaned),
                needs_retry=True,
                review_required=True,
                reason="Transcript did not clearly match a configured option.",
            )

        return AgentResult(
            question_id=question.question_id,
            raw_transcript=transcript,
            cleaned_text=cleaned,
            answer_type=question.answer_type,
            selected_option=None,
            confidence=0.75 if cleaned else 0.0,
            sentiment=self._sentiment(cleaned),
            keywords=self._keywords(cleaned),
            needs_retry=not bool(cleaned),
            review_required=not bool(cleaned),
            reason="Free-text answer accepted by mock analyzer." if cleaned else "Empty answer requires retry.",
        )

    def _match_option(self, question: SurveyQuestion, cleaned: str) -> str | None:
        normalized = cleaned.lower()
        for option in sorted(question.options, key=lambda item: len(item.label), reverse=True):
            if option.id == normalized or option.label.lower() in normalized:
                return option.id
        return None

    def _sentiment(self, cleaned: str) -> str:
        negative_terms = ["불만", "싫", "나쁘", "부족", "문제"]
        positive_terms = ["만족", "좋", "훌륭", "개선", "필요"]
        if any(term in cleaned for term in negative_terms):
            return "negative"
        if any(term in cleaned for term in positive_terms):
            return "positive"
        return "neutral" if cleaned else "unknown"

    def _keywords(self, cleaned: str) -> list[str]:
        tokens = [token.strip(".,!? ") for token in cleaned.split()]
        return [token for token in tokens if len(token) >= 2][:5]


class OllamaLLMProvider(LLMProvider):
    provider_name = "ollama"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate_json(self, *, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        if not self.settings.llm_base_url or not self.settings.llm_model:
            raise ProviderUnavailable("Ollama provider is not configured")
        url = self.settings.llm_base_url.rstrip("/") + "/api/generate"
        request = {
            "model": self.settings.llm_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_sec) as client:
                response = await client.post(url, json=request)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Ollama request failed: {exc}") from exc

        data = response.json()
        raw = data.get("response")
        if not raw:
            raise ProviderUnavailable("Ollama response did not include JSON text")
        return json.loads(raw)


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(self, *, provider_name: str, base_url: str, model: str, timeout_sec: float, api_key: str | None = None):
        self.provider_name = provider_name
        self.base_url = base_url
        self.model = model
        self.timeout_sec = timeout_sec
        self.api_key = api_key

    async def generate_json(self, *, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        if not self.base_url or not self.model:
            raise ProviderUnavailable(f"{self.provider_name} provider is not configured")
        if self.provider_name == "openai" and (not self.api_key or self.api_key == "replace_me"):
            raise ProviderUnavailable("OpenAI API key is not configured")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only JSON that matches the requested schema.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        url = self.base_url.rstrip("/") + "/v1/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                response = await client.post(url, headers=headers, json=request)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"{self.provider_name} request failed: {exc}") from exc

        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
