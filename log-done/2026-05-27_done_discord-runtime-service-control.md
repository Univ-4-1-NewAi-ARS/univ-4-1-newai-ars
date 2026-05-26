# Done — Discord Runtime Check And Service Control

## Summary

Validated the updated Discord guild/channel configuration, switched local runtime to real Discord mode, and added a service control script for Docker Compose services.

## Artifacts

- `scripts/services.sh` for per-service/group on/off/rebuild/status/logs/config commands
- README service control usage
- Discord bot `davey` dependency for voice support compatibility with the installed `discord.py`

## Tests

- `.env` Discord values checked with masked output only
- `docker compose config --quiet`: passed
- Orchestrator, STT, TTS, Dashboard health checks: passed
- Discord Gateway connection: passed
- Discord text channel lookup/send/delete: passed
- Discord voice channel lookup: passed
- `scripts/services.sh off dashboard` and `scripts/services.sh on dashboard`: passed
- `scripts/services.sh rebuild discord-bot`: passed
- `bash -n scripts/services.sh`: passed
- Discord bot tests: 4 passed
- AI Orchestrator tests: 14 passed

## Result

Discord text runtime is connected and channel IDs are valid. Voice dependency imports now pass inside the Discord bot container.

## Next

Run a manual Discord command test in the configured text channel:

```text
!survey start campus_opinion_survey
```
