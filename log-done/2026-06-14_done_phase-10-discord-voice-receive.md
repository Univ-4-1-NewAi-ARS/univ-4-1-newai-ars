# Done — Phase 10 Discord Voice Receive

## Summary

Implemented real Discord voice-answer capture. Spoken answers were previously
unrecognized because only a file-path command existed; now the bot records the user's
microphone and feeds it to STT.

## Artifacts

- `discord-ext-voice-recv` dependency (replaced unused `davey`)
- `VoiceRecorder` PCM buffer + wav encoder
- `!survey voice-listen` command with silence-based auto-stop
- `VOICE_SILENCE_TIMEOUT_SEC` / `VOICE_MAX_RECORD_SEC` settings
- `libopus0` in discord-bot image

## Tests

- discord-bot pytest: 8 passed

## Result

Voice answers are captured to wav and submitted to the existing STT/orchestrator flow;
`voice-file` remains as fallback.

## Next

Manual Discord smoke with a live token (join voice → `voice-listen` → speak → confirm
transcript). Optionally downmix to 16kHz mono for whisper accuracy.
