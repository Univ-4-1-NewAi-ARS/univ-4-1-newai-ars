# STT Enhancement — Whisper VAD + Anti-Hallucination

## Goal

Improve the local_whisper STT to stop silence/noise hallucinations and expose
quality knobs.

## Change (stt-service)

`LocalWhisperSTTProvider.transcribe` now passes configurable decoding params:

- `vad_filter=True` + `vad_parameters.min_silence_duration_ms` (Silero VAD trims silence)
- `no_speech_threshold=0.6`, `condition_on_previous_text=False`, `temperature=0.0`
- `beam_size` configurable; `STT_MODEL` documented for small→medium/large-v3 upgrade

Settings + `.env.example` updated (`STT_VAD_FILTER`, `STT_NO_SPEECH_THRESHOLD`, …).

## Verification (real captured wavs + espeak)

Direct faster-whisper compare (OLD = no VAD, NEW = VAD+no_speech) on real Discord
captures:

| input | OLD | NEW |
|---|---|---|
| noise fragment (1324B) | "구독과 좋아요 부탁드려요!" | (empty) |
| noise fragment (8044B) | "구독&좋아요&댓글 부탁드려요!" | (empty) |
| espeak continuous 1.31s | non-empty | non-empty (preserved) |

→ VAD suppresses YouTube-outro hallucinations while preserving continuous speech.

Tests: stt-service **6 passed** (+`test_local_whisper_passes_vad_and_antihallucination_kwargs`).

## CRITICAL finding (separate issue, must fix for voice path)

While verifying, found the real Discord captures are 0.04–0.25s **fragments** —
almost all audio is dropped. Cause: `discord.opus.OpusError: corrupted stream`
in voice_recv's PacketRouter (likely a voice encryption/protocol version mismatch
in the alpha `discord-ext-voice-recv`). Whisper returns empty on the fragments,
and `STT_USE_MOCK_FALLBACK=true` then **fabricated** plausible answers from the
q1/q2/q3 filename stem (`_mock_transcript_for_audio`). So the earlier "successful"
smoke transcripts ("만족합니다" / "도서관 좌석이 더 필요합니다" / "전반적으로 좋습니다")
were mock fabrications, NOT real STT.

Implications / follow-ups:
1. Fix opus capture (upgrade discord.py + discord-ext-voice-recv to support current
   Discord voice encryption: aead_xchacha20_poly1305_rtpsize). This is the real blocker.
2. Stop mock fabrication masking real failures: when whisper runs but detects no
   speech, return an empty/no-speech result instead of falling back to mock.

## Commit

feat(stt): whisper VAD + anti-hallucination decoding params
