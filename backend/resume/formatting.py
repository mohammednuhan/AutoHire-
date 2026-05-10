from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from schemas.api_schemas import (
    EducationItem,
    ExperienceItem,
    ProjectItem,
    ResumeProfile,
    SkillsProfile,
)


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "the",
    "this",
    "to",
    "with",
    "you",
    "your",
}


def format_skills(skills: SkillsProfile) -> dict[str, list[str]]:
    return skills.model_dump()


def format_experience(experience: Iterable[ExperienceItem]) -> list[dict[str, Any]]:
    return [
        {
            "company": item.company,
            "role": item.role,
            "start_date": item.start_date,
            "end_date": item.end_date,
            "is_current": item.is_current,
            "location": item.location,
            "description": item.description,
            "tech_stack": item.tech_stack,
        }
        for item in experience
    ]


def format_projects(projects: Iterable[ProjectItem]) -> list[dict[str, Any]]:
    return [
        {
            "name": item.name,
            "description": item.description,
            "tech_stack": item.tech_stack,
            "url": item.url,
            "duration": item.duration,
        }
        for item in projects
    ]


def format_education(education: Iterable[EducationItem]) -> list[dict[str, Any]]:
    return [
        {
            "institution": item.institution,
            "degree": item.degree,
            "field": item.field,
            "graduation_year": item.graduation_year,
            "gpa": item.gpa,
            "relevant_courses": item.relevant_courses,
        }
        for item in education
    ]


def format_full_profile(profile: ResumeProfile) -> str:
    return json.dumps(profile.model_dump(), indent=2, ensure_ascii=True)


def extract_key_phrases(description: str | None, max_phrases: int = 20) -> list[str]:
    if not description:
        return []

    normalized = re.sub(r"[^A-Za-z0-9+#.\s-]", " ", description)
    tokens = [token.strip(" -").lower() for token in normalized.split()]
    tokens = [token for token in tokens if len(token) > 2 and token not in _STOPWORDS]

    phrase_counts: dict[str, int] = {}
    for size in (3, 2):
        for index in range(0, max(len(tokens) - size + 1, 0)):
            phrase = " ".join(tokens[index : index + size])
            if any(word in _STOPWORDS for word in phrase.split()):
                continue
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

    for token in tokens:
        phrase_counts[token] = phrase_counts.get(token, 0) + 1

    ranked = sorted(phrase_counts.items(), key=lambda item: (-item[1], item[0]))
    return [phrase for phrase, _count in ranked[:max_phrases]]


def flatten_profile_terms(profile: ResumeProfile) -> set[str]:
    terms: set[str] = set()
    for values in profile.skills.model_dump().values():
        terms.update(_normalized(value) for value in values if value)
    for experience in profile.experience:
        terms.add(_normalized(experience.company))
        terms.add(_normalized(experience.role))
        terms.update(_normalized(item) for item in experience.tech_stack if item)
    for project in profile.projects:
        terms.add(_normalized(project.name))
        terms.update(_normalized(item) for item in project.tech_stack if item)
    for education in profile.education:
        terms.add(_normalized(education.institution))
        terms.add(_normalized(education.degree))
        if education.field:
            terms.add(_normalized(education.field))
    terms.update(_normalized(item) for item in profile.achievements if item)
    return {term for term in terms if term}


def _normalized(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())
