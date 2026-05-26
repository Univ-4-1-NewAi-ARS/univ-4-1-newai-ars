from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from app.orchestrator_client import OrchestratorClient


@dataclass
class ActiveSession:
    session_id: str
    current_question_id: str


class TextSurveyManager:
    def __init__(self, *, client: OrchestratorClient, default_survey_id: str):
        self.client = client
        self.default_survey_id = default_survey_id
        self.sessions: dict[str, ActiveSession] = {}

    async def start(self, *, conversation_key: str, discord_user_id: str, survey_id: str | None = None) -> str:
        participant_ref = self._participant_ref(discord_user_id)
        payload = await self.client.start_session(
            survey_id=survey_id or self.default_survey_id,
            participant_ref=participant_ref,
        )
        question = payload["current_question"]
        self.sessions[conversation_key] = ActiveSession(
            session_id=payload["session_id"],
            current_question_id=question["question_id"],
        )
        return self._format_question(question)

    async def answer(self, *, conversation_key: str, transcript: str) -> str:
        active = self.sessions.get(conversation_key)
        if not active:
            return "진행 중인 설문이 없습니다. 먼저 `!survey start`를 입력해 주세요."

        payload = await self.client.submit_answer(
            session_id=active.session_id,
            question_id=active.current_question_id,
            transcript=transcript,
        )
        status = payload["status"]
        result = payload["agent_result"]
        if status == "completed":
            summary = await self.client.get_summary(session_id=active.session_id)
            self.sessions.pop(conversation_key, None)
            return self._format_completion(result, summary)

        next_question = payload["next_question"]
        self.sessions[conversation_key] = ActiveSession(
            session_id=active.session_id,
            current_question_id=next_question["question_id"],
        )
        return self._format_answer_result(result) + "\n\n" + self._format_question(next_question)

    def _participant_ref(self, discord_user_id: str) -> str:
        digest = sha256(discord_user_id.encode("utf-8")).hexdigest()[:12]
        return f"discord:{digest}"

    def _format_question(self, question: dict) -> str:
        lines = [f"[{question['question_id']}] {question['text']}"]
        options = question.get("options") or []
        for option in options:
            lines.append(f"{option['id']}. {option['label']}")
        return "\n".join(lines)

    def _format_answer_result(self, result: dict) -> str:
        selected = result.get("selected_option") or "free_text"
        confidence = result.get("confidence", 0)
        return f"응답 저장: {selected} (confidence={confidence:.2f})"

    def _format_completion(self, result: dict, summary: dict) -> str:
        return (
            self._format_answer_result(result)
            + f"\n설문이 완료되었습니다. 총 {summary.get('response_count', 0)}개 응답이 저장되었습니다."
        )
