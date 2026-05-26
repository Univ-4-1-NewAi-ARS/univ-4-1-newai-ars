from __future__ import annotations

from pathlib import Path

from app.models import AgentResult, SurveyQuestion, TTSResult, TranscriptionResult


class MockLLMProvider:
    provider_name = "mock"

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


class MockSTTProvider:
    provider_name = "mock"

    async def transcribe(self, audio_path: str, language: str) -> TranscriptionResult:
        stem = Path(audio_path).stem.lower()
        text = "만족합니다"
        if "free" in stem or "q2" in stem:
            text = "도서관 좌석이 더 필요합니다"
        return TranscriptionResult(
            text=text,
            language=language,
            confidence=0.9,
            duration_sec=2.0,
            provider=self.provider_name,
        )


class MockTTSProvider:
    provider_name = "mock"

    async def synthesize(self, text: str, voice: str, survey_id: str, question_id: str) -> TTSResult:
        safe_voice = voice.replace("/", "_")
        return TTSResult(
            audio_path=f"/data/tts/{survey_id}-{question_id}-{safe_voice}.wav",
            duration_sec=max(1.0, min(len(text) / 8.0, 8.0)),
            provider=self.provider_name,
            cached=True,
        )
