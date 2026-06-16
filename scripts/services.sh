#!/bin/sh
set -eu
if (set -o pipefail) 2>/dev/null; then
  set -o pipefail
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_PROFILES="--profile dashboard --profile devtools --profile telephony"
CORE_SERVICES="postgres redis ai-orchestrator stt-service tts-service discord-bot"
ALL_SERVICES="postgres redis ai-orchestrator stt-service tts-service discord-bot dashboard adminer telephony-gateway"

usage() {
  cat <<'EOF'
Usage:
  scripts/services.sh on <service|group>...
  scripts/services.sh off <service|group>...
  scripts/services.sh restart <service|group>...
  scripts/services.sh rebuild <service|group>...
  scripts/services.sh logs <service|group>...
  scripts/services.sh status
  scripts/services.sh list
  scripts/services.sh config

Services:
  postgres redis ai-orchestrator stt-service tts-service discord-bot dashboard adminer telephony-gateway

Groups:
  core       postgres redis ai-orchestrator stt-service tts-service discord-bot
  speech     stt-service tts-service
  app        ai-orchestrator discord-bot dashboard
  telephony  ai-orchestrator telephony-gateway (phone-channel alternative to discord-bot)
  all        every service including dashboard, adminer, telephony-gateway

Examples:
  scripts/services.sh on core
  scripts/services.sh off dashboard
  scripts/services.sh rebuild discord-bot
  scripts/services.sh logs ai-orchestrator
EOF
}

expand_targets() {
  for target in "$@"; do
    case "$target" in
      core)
        printf '%s\n' $CORE_SERVICES
        ;;
      speech)
        printf '%s\n' stt-service tts-service
        ;;
      app)
        printf '%s\n' ai-orchestrator discord-bot dashboard
        ;;
      telephony)
        printf '%s\n' ai-orchestrator telephony-gateway
        ;;
      all)
        printf '%s\n' $ALL_SERVICES
        ;;
      postgres|redis|ai-orchestrator|stt-service|tts-service|discord-bot|dashboard|adminer|telephony-gateway)
        printf '%s\n' "$target"
        ;;
      *)
        echo "Unknown service or group: $target" >&2
        exit 2
        ;;
    esac
  done | awk '!seen[$0]++'
}

require_targets() {
  if [ "$#" -eq 0 ]; then
    echo "A service or group target is required." >&2
    usage >&2
    exit 2
  fi
}

cmd="${1:-help}"
shift || true

case "$cmd" in
  on|up|start)
    require_targets "$@"
    services="$(expand_targets "$@")"
    docker compose $COMPOSE_PROFILES up -d $services
    ;;
  off|stop)
    require_targets "$@"
    services="$(expand_targets "$@")"
    docker compose $COMPOSE_PROFILES stop $services
    ;;
  restart)
    require_targets "$@"
    services="$(expand_targets "$@")"
    docker compose $COMPOSE_PROFILES restart $services
    ;;
  rebuild)
    require_targets "$@"
    services="$(expand_targets "$@")"
    docker compose $COMPOSE_PROFILES up -d --build $services
    ;;
  logs)
    require_targets "$@"
    services="$(expand_targets "$@")"
    docker compose $COMPOSE_PROFILES logs --tail="${TAIL:-100}" -f $services
    ;;
  status|ps)
    docker compose $COMPOSE_PROFILES ps -a
    ;;
  list)
    printf '%s\n' $ALL_SERVICES
    ;;
  config)
    docker compose $COMPOSE_PROFILES config --quiet
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage >&2
    exit 2
    ;;
esac
