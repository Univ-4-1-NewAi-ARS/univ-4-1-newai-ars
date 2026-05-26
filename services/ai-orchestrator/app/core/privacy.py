from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


REDACTED_TEXT = "***"
TRANSCRIPT_REDACTED_TEXT = "[redacted:transcript-disabled]"

_SECRET_PATTERNS = (
    re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"(Bot\s+)[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b"),
)


def mask_sensitive_text(text: str | None, extra_secrets: Iterable[str | None] = ()) -> str | None:
    if text is None:
        return None

    masked = str(text)
    for secret in extra_secrets:
        if secret and secret != "replace_me" and len(secret) >= 4:
            masked = masked.replace(secret, REDACTED_TEXT)

    masked = _SECRET_PATTERNS[0].sub(r"\1***", masked)
    masked = _SECRET_PATTERNS[1].sub(r"\1***", masked)
    for pattern in _SECRET_PATTERNS[2:]:
        masked = pattern.sub(REDACTED_TEXT, masked)
    return masked


def normalize_participant_ref(participant_ref: str, salt: str | None = None) -> str:
    value = participant_ref.strip()
    lowered = value.lower()
    if lowered.startswith(("hash:", "discord_hash:", "masked:", "discord:masked")):
        return value

    prefix = "hash:"
    salt_value = "" if not salt or salt == "replace_me" else salt
    digest = hashlib.sha256(f"{salt_value}:{value}".encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}"


def retention_deadline(days: int) -> datetime:
    safe_days = max(days, 0)
    return datetime.now(timezone.utc) + timedelta(days=safe_days)


def is_path_inside(path: str | Path, root: str | Path) -> bool:
    resolved_path = Path(path).resolve(strict=False)
    resolved_root = Path(root).resolve(strict=False)
    return resolved_path == resolved_root or resolved_path.is_relative_to(resolved_root)
