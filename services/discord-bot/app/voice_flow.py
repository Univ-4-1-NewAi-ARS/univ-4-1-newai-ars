from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from app.orchestrator_client import NoSpeechDetected, OrchestratorClient


@dataclass
class VoiceSession:
    session_id: str
    current_question_id: str
    current_tts_path: str | None


class VoiceSurveyManager:
    def __init__(self, *, client: OrchestratorClient, default_survey_id: str):
        self.client = client
        self.default_survey_id = default_survey_id
        self.sessions: dict[str, VoiceSession] = {}

    async def start(self, *, conversation_key: str, discord_user_id: str, survey_id: str | None = None) -> dict:
        payload = await self.client.start_session(
            survey_id=survey_id or self.default_survey_id,
            participant_ref=self._participant_ref(discord_user_id),
            channel="discord_voice",
        )
        question = payload["current_question"]
        tts = payload.get("tts")
        self.sessions[conversation_key] = VoiceSession(
            session_id=payload["session_id"],
            current_question_id=question["question_id"],
            current_tts_path=tts["audio_path"] if tts else None,
        )
        return {
            "message": self._format_question(question, tts),
            "audio_path": tts["audio_path"] if tts else None,
        }

    def has_session(self, conversation_key: str) -> bool:
        return conversation_key in self.sessions

    async def submit_audio_file(self, *, conversation_key: str, audio_path: str) -> dict:
        active = self.sessions.get(conversation_key)
        if not active:
            return self._no_active_session()
        try:
            payload = await self.client.submit_audio_answer(
                session_id=active.session_id,
                question_id=active.current_question_id,
                audio_path=audio_path,
            )
        except NoSpeechDetected:
            return {
                "completed": False,
                "no_speech": True,
                "message": "음성을 인식하지 못했습니다. 다시 말씀해 주세요.",
                "audio_path": None,
            }
        return await self._apply_answer(conversation_key, active, payload)

    async def submit_text_answer(self, *, conversation_key: str, transcript: str) -> dict:
        """Hybrid mode: the question was spoken (TTS) but the answer arrives as text."""
        active = self.sessions.get(conversation_key)
        if not active:
            return self._no_active_session()
        payload = await self.client.submit_answer(
            session_id=active.session_id,
            question_id=active.current_question_id,
            transcript=transcript,
        )
        return await self._apply_answer(conversation_key, active, payload)

    async def _apply_answer(self, conversation_key: str, active: VoiceSession, payload: dict) -> dict:
        result = payload["agent_result"]
        if payload["status"] == "completed":
            summary = await self.client.get_summary(session_id=active.session_id)
            self.sessions.pop(conversation_key, None)
            return {
                "completed": True,
                "message": self._format_completion(result, summary),
                "audio_path": None,
            }

        question = payload["next_question"]
        tts = payload.get("tts")
        self.sessions[conversation_key] = VoiceSession(
            session_id=active.session_id,
            current_question_id=question["question_id"],
            current_tts_path=tts["audio_path"] if tts else None,
        )
        return {
            "completed": False,
            "message": self._format_answer_result(result) + "\n\n" + self._format_question(question, tts),
            "audio_path": tts["audio_path"] if tts else None,
        }

    def _no_active_session(self) -> dict:
        return {
            "completed": False,
            "message": "진행 중인 음성 설문이 없습니다. 먼저 `!survey voice-start`를 입력해 주세요.",
            "audio_path": None,
        }

    def _participant_ref(self, discord_user_id: str) -> str:
        digest = sha256(discord_user_id.encode("utf-8")).hexdigest()[:12]
        return f"discord:{digest}"

    def _format_question(self, question: dict, tts: dict | None) -> str:
        suffix = f"\nTTS: {tts['audio_path']}" if tts else ""
        return f"[voice:{question['question_id']}] {question['text']}{suffix}"

    def _format_answer_result(self, result: dict) -> str:
        selected = result.get("selected_option") or "free_text"
        confidence = result.get("confidence", 0)
        return f"음성 응답 저장: {selected} (confidence={confidence:.2f})"

    def _format_completion(self, result: dict, summary: dict) -> str:
        return (
            self._format_answer_result(result)
            + f"\n음성 설문이 완료되었습니다. 총 {summary.get('response_count', 0)}개 응답이 저장되었습니다."
        )
