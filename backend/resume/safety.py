from __future__ import annotations

import re


class ContentSafetyError(Exception):
    pass


INJECTION_PATTERNS = [
    r"ignore (previous|all|above) instructions",
    r"you are now",
    r"system:",
    r"assistant:",
    r"new instructions:",
    r"disregard",
]


def sanitize_user_content(text: str) -> str:
    sanitized = re.sub(r"<[^>]+>", "", text)
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, sanitized, flags=re.IGNORECASE):
            raise ContentSafetyError(pattern)
    return sanitized[:8000]
