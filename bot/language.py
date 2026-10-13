"""Guard against model answers written in a non-Latin script (Russian, Chinese, Arabic...)."""

import logging
import unicodedata
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

# Max share of letters allowed outside the Latin script (names, quotes, tickers may slip in).
_MAX_FOREIGN_RATIO = 0.2


def is_french_script(text: str) -> bool:
    """False if a significant share of the letters is not Latin (Cyrillic, CJK, Arabic, ...)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    foreign = sum(1 for c in letters if not unicodedata.name(c, "").startswith("LATIN"))
    return foreign / len(letters) <= _MAX_FOREIGN_RATIO


def force_french(fn: Callable[[str], Awaitable[str]], attempts: int = 2) -> Callable[[str], Awaitable[str]]:
    """Wrap a text->text AI call: retry when the answer is not in Latin script, else return ""."""

    async def wrapper(text: str) -> str:
        for attempt in range(1, attempts + 1):
            answer = await fn(text)
            if not answer or is_french_script(answer):
                return answer
            logger.warning("Answer not in French (attempt %d/%d): %.80s", attempt, attempts, answer)
        return ""

    return wrapper
