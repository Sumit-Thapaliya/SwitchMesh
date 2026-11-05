"""Lightweight payload redaction for SwitchTrust boundaries."""

from __future__ import annotations

import re


_SECRET_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_ -]?key|access[_ -]?token|auth[_ -]?token|secret)\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]+\b", re.IGNORECASE),
)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d ().-]{6,}\d)(?!\d)")


def sanitize_payload(text: str) -> str:
    """Redact common sensitive values and append a SwitchTrust badge.

    The return value remains plain text so callers can safely log or forward it.
    A badge is appended only when one or more categories were redacted.
    """

    sanitized = str(text)
    categories: list[str] = []

    for pattern in _SECRET_PATTERNS:
        sanitized, count = pattern.subn("[REDACTED_SECRET]", sanitized)
        if count and "secret" not in categories:
            categories.append("secret")

    sanitized, count = _EMAIL_RE.subn("[REDACTED_EMAIL]", sanitized)
    if count:
        categories.append("email")

    sanitized, count = _CARD_RE.subn("[REDACTED_CARD]", sanitized)
    if count:
        categories.append("card")

    sanitized, count = _PHONE_RE.subn("[REDACTED_PHONE]", sanitized)
    if count:
        categories.append("phone")

    if not categories:
        return sanitized
    return f"{sanitized} — SwitchTrust Redacted ({', '.join(categories)})"
