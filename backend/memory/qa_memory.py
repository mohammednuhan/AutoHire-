from __future__ import annotations

import hashlib
import logging
import re
import string
from datetime import datetime, timezone

from sqlalchemy import select

from database.models import QAMemory
from database.session import AsyncSessionLocal

logger = logging.getLogger("autohire.memory.qa")

try:
    from nltk.stem import PorterStemmer

    _stemmer = PorterStemmer()
except Exception:  # pragma: no cover - dependency fallback
    _stemmer = None


def normalize_question(question: str) -> str:
    lowered = question.lower().translate(str.maketrans("", "", string.punctuation))
    tokens = re.sub(r"\s+", " ", lowered).strip().split()
    if _stemmer is not None:
        tokens = [_stemmer.stem(token) for token in tokens]
    return " ".join(tokens)


def hash_question(question: str) -> str:
    normalized = normalize_question(question)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def retrieve_similar_answer(question: str) -> str | None:
    question_hash = hash_question(question)
    async with AsyncSessionLocal() as db:
        result = await db.scalar(select(QAMemory).where(QAMemory.question_hash == question_hash))
        if result is None:
            return None
        result.used_count = (result.used_count or 0) + 1
        result.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("qa_memory_cache_hit", extra={"question_hash": question_hash})
        return result.answer_text


async def save_answer(
    question: str,
    answer: str,
    category: str,
    board: str,
    company: str,
) -> None:
    question_hash = hash_question(question)
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(QAMemory).where(QAMemory.question_hash == question_hash))
        if existing is None:
            db.add(
                QAMemory(
                    question_hash=question_hash,
                    question_text=question,
                    question_category=category,
                    answer_text=answer,
                    confidence=1.0,
                    board=board,
                    company=company,
                    used_count=1,
                )
            )
        else:
            existing.answer_text = answer
            existing.question_category = category
            existing.board = board
            existing.company = company
            existing.last_used_at = datetime.now(timezone.utc)
        await db.commit()
