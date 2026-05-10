from __future__ import annotations

import re

import bleach


class ContentSafetyError(Exception):
    pass


INJECTION_PATTERNS = [
    r"ignore (previous|all|above) instructions",
    r"you are now",
    r"new (system|instructions|prompt):",
    r"disregard (all|previous)",
    r"\[INST\]|\[/INST\]",
    r"<\|im_start\|>",
    r"Human:|Assistant:",
    r"<system>|</system>",
    r"override (previous|current)",
]


def sanitize_user_content(text: str) -> str:
    sanitized = bleach.clean(text or "", tags=[], strip=True)
    sanitized = re.sub(r"<[^>]+>", "", sanitized)
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, sanitized, flags=re.IGNORECASE):
            raise ContentSafetyError(pattern)
    return sanitized[:8000]
