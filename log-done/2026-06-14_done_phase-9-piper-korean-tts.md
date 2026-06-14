# Done — Phase 9 Piper Korean TTS Enablement

## Summary

Activated the real `local_piper` TTS path with a provisioned Korean voice model and
kept the espeak/cached fallback chain.

## Artifacts

- `scripts/provision_piper.sh` voice provisioning (default: community KSS Korean)
- `piper-tts` CLI in tts-service image
- Korean default `PIPER_MODEL_PATH=/models/piper/piper-kss-korean.onnx`
- `local_piper` success-path unit test
- Updated provider strategy, phase plan, env rules, README

## Tests

- TTS service pytest: 5 passed

## Result

`local_piper` is a real, testable provider; Korean voice assets are provisioned
out-of-repo via script with fallback preserved on failure.

## Next

Download the model with `scripts/provision_piper.sh`, run Docker runtime smoke with
`TTS_PROVIDER=local_piper`, then extend Discord voice receive beyond file-based fallback.
