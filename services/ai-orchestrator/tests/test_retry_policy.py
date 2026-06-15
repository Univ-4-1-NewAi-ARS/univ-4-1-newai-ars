from app.core.settings import Settings
from app.models import AgentResult, SurveyQuestion
from app.services.orchestrator import OrchestratorService


def _result(needs_retry: bool, answer_type: str) -> AgentResult:
    return AgentResult(
        question_id="q2",
        raw_transcript="도서관 좌석이 더 필요합니다",
        cleaned_text="도서관 좌석이 더 필요합니다",
        answer_type=answer_type,
        selected_option=None,
        confidence=0.85,
        sentiment="negative",
        keywords=["도서관"],
        needs_retry=needs_retry,
        review_required=needs_retry,
        reason="test",
    )


FREE_TEXT_Q = SurveyQuestion(question_id="q2", text="개선이 필요한 영역은?", answer_type="free_text", options=[])
SINGLE_CHOICE_Q = SurveyQuestion(
    question_id="q1",
    text="만족하시나요?",
    answer_type="single_choice",
    options=[{"id": "1", "label": "만족"}, {"id": "2", "label": "불만족"}],
)


def _service(free_text_retry_enabled: bool) -> OrchestratorService:
    service = OrchestratorService.__new__(OrchestratorService)
    service.settings = Settings(repository_provider="memory", free_text_retry_enabled=free_text_retry_enabled)
    return service


def test_free_text_does_not_retry_even_when_llm_flags_needs_retry() -> None:
    service = _service(free_text_retry_enabled=False)
    # The live bug: gemma3:4b returned needs_retry=True on a valid free_text answer.
    assert service._should_retry(FREE_TEXT_Q, _result(True, "free_text")) is False


def test_single_choice_still_retries_on_needs_retry() -> None:
    service = _service(free_text_retry_enabled=False)
    assert service._should_retry(SINGLE_CHOICE_Q, _result(True, "single_choice")) is True
    assert service._should_retry(SINGLE_CHOICE_Q, _result(False, "single_choice")) is False


def test_free_text_retry_can_be_re_enabled_by_setting() -> None:
    service = _service(free_text_retry_enabled=True)
    assert service._should_retry(FREE_TEXT_Q, _result(True, "free_text")) is True
