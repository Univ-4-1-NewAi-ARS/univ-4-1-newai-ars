import pytest

from app.providers.mock import MockLLMProvider
from app.survey_loader import SurveyLoader
from conftest import SURVEY_DIR


@pytest.mark.asyncio
async def test_mock_agent_maps_single_choice() -> None:
    survey = SurveyLoader(SURVEY_DIR).load("campus_opinion_survey")
    question = survey.get_question("q1")

    result = await MockLLMProvider().analyze_answer(question, "만족합니다")

    assert result.selected_option == "2"
    assert result.needs_retry is False
    assert result.review_required is False


@pytest.mark.asyncio
async def test_mock_agent_marks_unclear_choice_for_retry() -> None:
    survey = SurveyLoader(SURVEY_DIR).load("campus_opinion_survey")
    question = survey.get_question("q1")

    result = await MockLLMProvider().analyze_answer(question, "잘 모르겠습니다")

    assert result.selected_option is None
    assert result.needs_retry is True
    assert result.review_required is True
