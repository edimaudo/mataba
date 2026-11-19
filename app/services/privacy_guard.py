"""Server-side defence-in-depth for obvious PII left in client-sanitized text.

This does not replace local Gemini Nano/pattern screening or the user's manual
review. It blocks high-confidence residual identifiers without recording values.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from fastapi import HTTPException


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("SIN-like number", re.compile(r"\b\d{3}[ -]?\d{3}[ -]?\d{3}\b")),
    ("phone number", re.compile(r"(?:\+?1[ .-]?)?(?:\(?[2-9]\d{2}\)?[ .-]?)\d{3}[ .-]\d{4}\b")),
    ("Canadian postal code", re.compile(r"\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ -]?\d[ABCEGHJ-NPRSTV-Z]\d\b", re.IGNORECASE)),
)


def find_residual_categories(texts: Iterable[str]) -> list[str]:
    joined = "\n".join(texts)
    return [label for label, pattern in _PATTERNS if pattern.search(joined)]


def require_sanitized_text(texts: Iterable[str], language: str) -> None:
    categories = find_residual_categories(texts)
    if not categories:
        return
    if language == "fr":
        message = (
            "Des renseignements personnels potentiels subsistent dans le texte expurgé. "
            "Retournez à la protection locale, ajoutez des masquages manuels et vérifiez le texte avant de continuer."
        )
    else:
        message = (
            "Potential personal identifiers remain in the sanitized text. Return to the Local Privacy Shield, "
            "add manual redactions, and review the text before continuing."
        )
    # Do not include matched values or excerpts in API messages or logs.
    raise HTTPException(status_code=422, detail=message)
