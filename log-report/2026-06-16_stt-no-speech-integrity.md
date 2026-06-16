# STT Integrity — Stop Mock Fabrication on No-Speech

## Problem

With the Discord captures reduced to fragments (DAVE blocker), whisper returned
empty and the chain fell back to `mock`, which fabricated answers from the
q1/q2/q3 filename stem. This masked the broken capture as "successful" surveys.

## Fix (honest no-speech, no fabrication)

- **stt-service**: `TranscribeResponse.no_speech`; setting
  `stt_fabricate_on_no_speech=False`. When whisper runs but returns empty text, the
  provider now returns `text="", no_speech=True, provider=local_whisper` instead of
  raising → no mock fabrication. Genuine errors (file missing/model fail) still raise
  → fallback chain unchanged.
- **ai-orchestrator**: when STT yields empty text for provided audio, `submit_answer`
  records an `answer_no_speech` audit event and raises **HTTP 422** — nothing stored,
  session stays on the same question.
- **discord-bot**: `OrchestratorClient` raises `NoSpeechDetected` on 422;
  `VoiceSurveyManager.submit_audio_file` returns a `no_speech` signal; the voice loop
  treats it like an empty capture (re-ask, count toward the 3-strike stop).

## Tests

- stt-service **7** (+`no_speech_does_not_fabricate`)
- ai-orchestrator **22** (+`test_no_speech` 422/no-store/audit)
- discord-bot **13** (+no_speech signal, +client raises NoSpeechDetected)

## Live verification

Submitting a real 0.04s fragment (stem `q1`, which mock WOULD turn into "만족합니다"):
→ HTTP 422 "No speech detected", 0 stored responses, `answer_no_speech` in
`/audit/events`. Failures are now visible in the dashboard /logs instead of faked.

## Commit

feat(stt): honest no-speech result, stop mock fabrication (422 + audit)
