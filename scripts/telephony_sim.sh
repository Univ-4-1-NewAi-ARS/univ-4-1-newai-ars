#!/bin/sh
# Local Twilio-call simulator for the telephony-gateway.
#
# Drives the webhook flow against a RUNNING gateway by POSTing the same
# form-encoded payloads Twilio would send, so the full phone survey can be
# verified end-to-end with no Twilio account and no real phone.
#
# Usage:
#   scripts/telephony_sim.sh [GATEWAY_URL] [FROM_NUMBER] [ANSWER ...]
#
# Examples:
#   scripts/telephony_sim.sh
#   scripts/telephony_sim.sh http://localhost:8300 +821012345678 "매우 만족" "주차 공간" "전반적으로 좋습니다"
#
# Requires: curl. The gateway must be up (scripts/services.sh on telephony-gateway
# or: docker compose up -d --build telephony-gateway ai-orchestrator ...).
set -eu

GATEWAY="${1:-http://localhost:8300}"
FROM="${2:-+821012345678}"
shift 2 2>/dev/null || true

# Remaining args are spoken answers, cycled if fewer than the question count.
if [ "$#" -gt 0 ]; then
  ANSWERS="$*"
else
  ANSWERS="매우 만족합니다|주차 공간이 부족합니다|전반적으로 만족스럽습니다"
fi

CALL_SID="CAsim$(date +%s)"
MAX_TURNS="${MAX_TURNS:-12}"

echo "== Telephony simulation =="
echo "gateway:  $GATEWAY"
echo "from:     $FROM (will be hashed to phone:{digest} by the gateway)"
echo "call_sid: $CALL_SID"
echo

echo "--- POST /voice/incoming ---"
RESP="$(curl -s -X POST "$GATEWAY/voice/incoming" \
  --data-urlencode "CallSid=$CALL_SID" \
  --data-urlencode "From=$FROM")"
echo "$RESP"
echo

turn=1
while [ "$turn" -le "$MAX_TURNS" ]; do
  case "$RESP" in
    *"<Hangup/>"*)
      echo "== survey completed (Hangup) after $turn turn(s) =="
      exit 0
      ;;
    *"<Gather"*) : ;;  # expected: keep answering
    *)
      echo "!! No <Gather> and no <Hangup/> in response; stopping." >&2
      exit 1
      ;;
  esac

  # Pick the answer for this turn (1-indexed into the '|'-separated list, cycling).
  ANSWER="$(printf '%s' "$ANSWERS" | awk -v n="$turn" -F'|' '{ idx=((n-1)%NF)+1; print $idx }')"

  echo "--- POST /voice/answer (turn $turn, SpeechResult=\"$ANSWER\") ---"
  RESP="$(curl -s -X POST "$GATEWAY/voice/answer" \
    --data-urlencode "CallSid=$CALL_SID" \
    --data-urlencode "SpeechResult=$ANSWER")"
  echo "$RESP"
  echo
  turn=$((turn + 1))
done

echo "!! Reached MAX_TURNS=$MAX_TURNS without completion." >&2
exit 1
