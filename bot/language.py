"""Model-based guard: a message must be written in French before it is sent."""

import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

FRENCH_PROMPT = (
    "Ce texte est-il rédigé entièrement en français (hors noms propres, sigles, tickers et "
    "citations très courtes) ? Toute autre langue différente du français est NON.\n"
    "Réponds uniquement par 'OUI' ou 'NON'.\n\n"
)

TextFn = Callable[[str], Awaitable[str]]
CheckFn = Callable[[str], Awaitable[bool]]


def is_yes(answer: str) -> bool:
    """Parse a OUI/YES answer, tolerating quotes and markdown around it."""
    return answer.strip().strip("'\".*").upper().startswith(("OUI", "YES"))


def force_french(fn: TextFn, check: CheckFn, attempts: int = 2) -> TextFn:
    """Wrap a text->text AI call: retry when the answer is not French, else return ""."""

    async def wrapper(text: str) -> str:
        for attempt in range(1, attempts + 1):
            answer = await fn(text)
            if not answer:
                return ""
            if await check(answer):
                return answer
            logger.warning("Answer not in French (attempt %d/%d): %.80s", attempt, attempts, answer)
        return ""

    return wrapper
