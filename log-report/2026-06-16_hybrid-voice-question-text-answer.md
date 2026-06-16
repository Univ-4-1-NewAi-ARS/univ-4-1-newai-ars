# Hybrid Voice-Question + Text-Answer Mode (DAVE bypass, low-difficulty)

## Goal

A low-difficulty voice-ARS-like flow that works around Discord DAVE (which blocks
audio receive) and showcases GPT-SoVITS — without telephony infra.

## Approach

DAVE blocks RECEIVE only; Discord audio SEND (playback) still works. So: the bot
**speaks each question** (TTS, GPT-SoVITS-capable) in the voice channel and the
user **answers with `!survey answer <text>`**. No mic capture, no telephony.

## Change (discord-bot)

- `VoiceSurveyManager`: extracted `_apply_answer`/`_no_active_session`; added
  `submit_text_answer` (spoken question, text answer) and `has_session`.
- `Settings.voice_answer_mode` (`VOICE_ANSWER_MODE`, default `text`).
- `main.py`:
  - `voice-start` → `text` mode: speak q1 (`_play_tts_only`), prompt for
    `!survey answer`; `audio` mode keeps the legacy (DAVE-broken) capture loop.
  - `!survey answer` routes to the active voice session via `submit_text_answer`
    (then plays the next question TTS) when one exists; else the plain text survey.

## GPT-SoVITS

The spoken questions use whatever `TTS_PROVIDER` is set. With `TTS_PROVIDER=gpt_sovits`
(+ a running GPT-SoVITS api_v2 server + ref audio), questions use the cloned voice;
otherwise espeak. The provider was added previously; the hybrid flow exercises it on
the SEND path, which DAVE does not block.

## Tests

discord-bot **15 passed** (+`hybrid_text_answer_advances_and_completes`,
+`submit_text_answer_without_session`).

## Live verification

Orchestrator hybrid path (discord_voice session + text answers): q1→q2→q3→completed,
each next question carries a TTS audio_path (local_espeak). Bot reconnected live.
Full Discord-side demo (type voice-start, hear question, type answer) is DAVE-safe
because it never receives audio.

## Commit

feat(bot): hybrid spoken-question + text-answer voice mode (DAVE bypass)
