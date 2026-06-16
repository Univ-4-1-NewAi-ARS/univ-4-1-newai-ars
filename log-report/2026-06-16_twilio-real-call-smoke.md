# Real Twilio Call Smoke — Telephony Gateway (Phase 11a)

## Setup

- Exposed `telephony-gateway` (:8300) via a cloudflared quick tunnel (no account):
  `https://<random>.trycloudflare.com`.
- Configured the Twilio number `+1 945 292 9037` (account Trial, $14.35) via the REST
  API: `VoiceUrl = https://<tunnel>/voice/incoming` (POST), `VoiceFallbackUrl` same.
- Placed an outbound call from the Twilio number to the account's **verified** Korean
  number (trial accounts can only reach verified numbers) with
  `Url=https://<tunnel>/voice/incoming`.

## Result — end-to-end SUCCESS

- Twilio call: `status=completed`, `duration=73s`.
- Gateway log: `POST /voice/incoming 200` + `POST /voice/answer 200` ×4.
- Session persisted: `channel=phone`, `actor=hash:...` (raw caller number NOT stored),
  `status=completed`, 4 responses (q1 asked twice = one retry).

Captured answers (Twilio's ko-KR cloud STT → our LLM analysis):

| question | Twilio transcript | analysis |
|---|---|---|
| q1 (1st) | "성당이 만두." | no option match → re-asked |
| q1 (retry) | "만족!" | matched option 1, positive |
| q2 | "AI 문자 주세요." | free_text, neutral |
| q3 | "반대." | free_text, negative |

The full pipeline ran over a real phone: PSTN → Twilio (TTS + STT) → tunnel →
telephony-gateway → orchestrator (ollama gemma3:4b) → PostgreSQL → completed. The
single_choice retry logic worked (q1's first garbled transcript didn't match → re-ask
→ "만족!" matched).

## Key finding — Twilio narrowband Korean STT accuracy is poor

Several answers were mis-transcribed ("성당이 만두", "AI 문자 주세요") — the known
limitation of 8 kHz phone audio + Twilio cloud STT for Korean. The system handled it
gracefully (retry on no match), but answer fidelity is low.

→ Mitigation path: **Option B (Twilio Media Streams + local whisper, Phase 11b)** keeps
STT local and avoids Twilio's recognizer; also better for privacy. Designed in docs/08,
not yet implemented.

## Notes

- The cloudflared quick-tunnel URL is ephemeral — if the tunnel restarts, re-point the
  Twilio VoiceUrl.
- The Twilio Auth Token was shared in chat → rotate it in the console after testing.
