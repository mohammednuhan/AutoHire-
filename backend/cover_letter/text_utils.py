from __future__ import annotations

import json
import re
from typing import Any


BANNED_PHRASES = {
    "passionate about",
    "quick learner",
    "great fit",
    "i am writing to apply for",
    "team player",
    "go-getter",
    "results-driven",
    "synergy",
}


def json_payload(response: str) -> dict[str, Any]:
    text = response.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'+.-]+\b", text))


def paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    chunks = re.split(r"\n\s*\n+", normalized)
    return [re.sub(r"\s+", " ", chunk).strip() for chunk in chunks if chunk.strip()]


def banned_phrase_hits(text: str) -> list[str]:
    lower_text = text.lower()
    return sorted(phrase for phrase in BANNED_PHRASES if phrase in lower_text)


def opens_with_i(text: str) -> bool:
    match = re.search(r"[A-Za-z]+", text)
    return bool(match and match.group(0).lower() == "i")
