from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from app.core.privacy import mask_sensitive_text
from app.core.settings import Settings
from app.models import AgentResult, SurveyQuestion
from app.providers.llm import LLMProvider, ProviderUnavailable
from app.providers.llm_router import LLMRouter


@dataclass(frozen=True)
class AgentRunResult:
    result: AgentResult
    provider: str
    retry_count: int
    fallback_used: bool
    error_message: str | None = None


class AnswerAnalyzer:
    def __init__(self, *, settings: Settings, router: LLMRouter):
        self.settings = settings
        self.router = router

    async def analyze_answer(self, question: SurveyQuestion, transcript: str) -> AgentRunResult:
        prompt = self._build_prompt(question, transcript)
        providers = self.router.providers_for_request()
        primary_name = providers[0].provider_name
        last_error: str | None = None

        for provider in providers:
            for retry_index in range(self.settings.llm_parse_retry_count + 1):
                try:
                    payload = await provider.generate_json(prompt=prompt, schema=AgentResult)
                    result = AgentResult.model_validate(payload)
                    return AgentRunResult(
                        result=result,
                        provider=provider.provider_name,
                        retry_count=retry_index,
                        fallback_used=provider.provider_name != primary_name or last_error is not None,
                        error_message=last_error,
                    )
                except ProviderUnavailable as exc:
                    last_error = self._mask_error(exc)
                    break
                except (ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
                    last_error = self._mask_error(exc)
                    if retry_index >= self.settings.llm_parse_retry_count:
                        break

        mock_provider = self.router.mock_provider()
        payload = await mock_provider.generate_json(prompt=prompt, schema=AgentResult)
        result = AgentResult.model_validate(payload)
        return AgentRunResult(
            result=result,
            provider=mock_provider.provider_name,
            retry_count=0,
            fallback_used=True,
            error_message=last_error,
        )

    def _build_prompt(self, question: SurveyQuestion, transcript: str) -> str:
        return json.dumps(
            {
                "task": "analyze_survey_answer",
                "schema": "AgentResult",
                "question": question.model_dump(mode="json"),
                "transcript": transcript,
            },
            ensure_ascii=False,
        )

    def _mask_error(self, exc: Exception) -> str:
        text = mask_sensitive_text(str(exc), extra_secrets=[self.settings.openai_api_key]) or ""
        return text[:500]
