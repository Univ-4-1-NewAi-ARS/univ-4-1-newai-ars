# TTS Enhancement — GPT-SoVITS Voice-Cloning Provider

## Goal

Add GPT-SoVITS (voice-cloning TTS) as a selectable TTS provider for higher-quality
Korean question playback.

## Change (tts-service)

- New `gpt_sovits` provider: HTTP adapter to a GPT-SoVITS `api_v2` server
  (`POST /tts`). Sends target text + reference audio path + reference transcript +
  lang/speed/split params; saves the returned wav to `/data/tts`.
- Settings: `GPT_SOVITS_BASE_URL` (default host.docker.internal:9880),
  `GPT_SOVITS_REF_AUDIO_PATH`, `GPT_SOVITS_REF_TEXT`, `REF_LANG`, `TEXT_LANG`,
  `TEXT_SPLIT`, `SPEED`, `TIMEOUT_SEC`.
- `httpx` added to tts-service deps. HTTP call isolated in `_post_for_audio` for
  testability; actual wav duration read via `_wav_duration`.
- Graceful degrade: unconfigured ref / unreachable server / HTTP error all raise
  `ProviderUnavailable` → existing fallback chain (`tts_fallback_provider` →
  `cached_file`). The heavy model runs on a separate server; repo holds only the
  adapter (no model assets committed).

## Design notes

- Reference audio/text resolve on the GPT-SoVITS server, not in tts-service.
- When `gpt_sovits` is primary, set `TTS_FALLBACK_PROVIDER=local_espeak` so failures
  fall back to real Korean audio rather than silent cached wav.

## Tests

tts-service **8 passed** (+3): synthesizes from mocked server (payload carries ref +
text + lang), unconfigured → cached fallback, HTTP error → cached fallback.

## Live verification

- `provider=gpt_sovits` with no server → gracefully falls back (cached_file,
  fallback_used=true), no crash.
- default `local_espeak` still synthesizes (fallback_used=false).
- Full GPT-SoVITS audio output is pending a running GPT-SoVITS server (separate
  install); the adapter + fallback are complete and verified.

## Commit

feat(tts): GPT-SoVITS voice-cloning provider with graceful fallback
