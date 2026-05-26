from app.agents.answer_analyzer import AnswerAnalyzer
from app.core.settings import Settings
from app.providers.llm_router import LLMRouter
from app.providers.llm import ProviderUnavailable
from app.survey_loader import SurveyLoader
from conftest import SURVEY_DIR


def test_llm_router_uses_mock_when_configured() -> None:
    router = LLMRouter(Settings(repository_provider="memory", survey_dir=SURVEY_DIR, llm_provider="mock"))

    providers = router.providers_for_request()

    assert [provider.provider_name for provider in providers] == ["mock"]


async def test_unavailable_ollama_gracefully_falls_back_to_mock() -> None:
    settings = Settings(
        repository_provider="memory",
        survey_dir=SURVEY_DIR,
        llm_provider="ollama",
        llm_base_url="http://127.0.0.1:1",
        llm_use_api_fallback=False,
    )
    analyzer = AnswerAnalyzer(settings=settings, router=LLMRouter(settings))
    question = SurveyLoader(SURVEY_DIR).load("campus_opinion_survey").get_question("q1")

    run = await analyzer.analyze_answer(question, "만족합니다")

    assert run.provider == "mock"
    assert run.fallback_used is True
    assert run.result.selected_option == "2"


async def test_mock_fallback_can_be_disabled() -> None:
    settings = Settings(
        repository_provider="memory",
        survey_dir=SURVEY_DIR,
        llm_provider="ollama",
        llm_base_url="http://127.0.0.1:1",
        llm_use_api_fallback=False,
        llm_use_mock_fallback=False,
    )
    analyzer = AnswerAnalyzer(settings=settings, router=LLMRouter(settings))
    question = SurveyLoader(SURVEY_DIR).load("campus_opinion_survey").get_question("q1")

    try:
        await analyzer.analyze_answer(question, "만족합니다")
    except ProviderUnavailable:
        return

    raise AssertionError("Expected ProviderUnavailable when all fallbacks are disabled")
