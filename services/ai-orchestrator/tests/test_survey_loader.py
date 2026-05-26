import pytest

from app.survey_loader import SurveyLoader, SurveyNotFoundError
from conftest import SURVEY_DIR


def test_loads_campus_survey() -> None:
    survey = SurveyLoader(SURVEY_DIR).load("campus_opinion_survey")

    assert survey.survey_id == "campus_opinion_survey"
    assert survey.first_question().question_id == "q1"
    assert survey.first_question().options[1].label == "만족"


def test_missing_survey_raises() -> None:
    with pytest.raises(SurveyNotFoundError):
        SurveyLoader(SURVEY_DIR).load("missing")
