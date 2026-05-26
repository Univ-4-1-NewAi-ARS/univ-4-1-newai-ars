from __future__ import annotations

from app.core.settings import Settings
from app.providers.llm import LLMProvider, MockLLMProvider, OllamaLLMProvider, OpenAICompatibleLLMProvider


class LLMRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._mock = MockLLMProvider()

    def providers_for_request(self) -> list[LLMProvider]:
        primary = self._provider_for_name(self.settings.llm_provider)
        providers: list[LLMProvider] = [primary]

        if self.settings.llm_use_api_fallback and self.settings.openai_api_key != "replace_me":
            providers.append(self._openai_provider())

        if primary.provider_name != "mock":
            providers.append(self._mock)

        return self._dedupe(providers)

    def mock_provider(self) -> MockLLMProvider:
        return self._mock

    def _provider_for_name(self, name: str) -> LLMProvider:
        normalized = name.lower()
        if normalized == "mock":
            return self._mock
        if normalized == "ollama":
            return OllamaLLMProvider(self.settings)
        if normalized == "lmstudio":
            return OpenAICompatibleLLMProvider(
                provider_name="lmstudio",
                base_url=self.settings.llm_base_url,
                model=self.settings.llm_model,
                timeout_sec=self.settings.llm_timeout_sec,
            )
        if normalized == "openai":
            return self._openai_provider()
        return self._mock

    def _openai_provider(self) -> OpenAICompatibleLLMProvider:
        return OpenAICompatibleLLMProvider(
            provider_name="openai",
            base_url="https://api.openai.com",
            model=self.settings.openai_model,
            timeout_sec=self.settings.llm_timeout_sec,
            api_key=self.settings.openai_api_key,
        )

    def _dedupe(self, providers: list[LLMProvider]) -> list[LLMProvider]:
        seen: set[str] = set()
        deduped: list[LLMProvider] = []
        for provider in providers:
            if provider.provider_name in seen:
                continue
            seen.add(provider.provider_name)
            deduped.append(provider)
        return deduped
