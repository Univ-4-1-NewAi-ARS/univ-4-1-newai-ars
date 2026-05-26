from pathlib import Path

import yaml

from app.models import SurveyDefinition


class SurveyNotFoundError(KeyError):
    pass


class SurveyLoader:
    def __init__(self, survey_dir: Path):
        self.survey_dir = survey_dir

    def load(self, survey_id: str) -> SurveyDefinition:
        path = self.survey_dir / f"{survey_id}.yaml"
        if not path.exists():
            raise SurveyNotFoundError(f"Survey definition not found: {survey_id}")

        with path.open("r", encoding="utf-8") as file:
            payload = yaml.safe_load(file) or {}

        survey = SurveyDefinition.model_validate(payload)
        if survey.survey_id != survey_id:
            raise ValueError(f"Survey id mismatch: expected {survey_id}, got {survey.survey_id}")
        if not survey.questions:
            raise ValueError(f"Survey has no questions: {survey_id}")
        return survey
