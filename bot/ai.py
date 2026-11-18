"""The bot's AI capabilities, each a FallbackChain over the configured providers."""

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from bot.fallback import Capability, FallbackChain, Provider
from bot.prompts import (
    CLASSIFY_PROMPT,
    FRENCH_PROMPT,
    PROMO_PROMPT,
    RELEVANCE_PROMPT,
    SUMMARY_PROMPT,
    TRANSLATE_PROMPT,
)

_SHORT = 1024  # even for one-word answers: reasoning tokens, if any, count against the limit
_ID = lambda s: s  # noqa: E731


class TranslationError(Exception):
    """No provider produced a valid French translation."""


def is_yes(answer: str) -> bool:
    """Parse a OUI/YES answer (the model may answer in the tweet's language), tolerating quotes
    and markdown around it."""
    return answer.strip().strip("'\".*").upper().startswith(("OUI", "YES"))


@dataclass
class AI:
    """Async callables used by the tweet pipeline; all None when no provider is configured."""
    translate: Optional[Callable[[str], Awaitable[str]]] = None
    summarize: Optional[Callable[[str], Awaitable[str]]] = None
    is_relevant: Optional[Callable[[str], Awaitable[bool]]] = None
    is_promotional: Optional[Callable[[str], Awaitable[bool]]] = None
    is_french: Optional[Callable[[str], Awaitable[bool]]] = None
    classify: Optional[Callable[[str], Awaitable[str]]] = None


def build_ai(providers: list[Provider], sleep=asyncio.sleep) -> AI:
    """Providers are tried in the given order for every capability."""
    if not providers:
        return AI()

    def chain(cap: Capability) -> FallbackChain:
        return FallbackChain(cap, providers, sleep=sleep)

    # Failure policy per capability, in one place:
    #   translate/summarize: nothing is sent when no valid French text (raise / "")
    #   relevance: fail open (True)  promotion: fail open (not promotional)  French check: fail closed
    is_french = chain(Capability("french-check", FRENCH_PROMPT, _SHORT, is_yes, lambda t: False,
                                 default=False, retry_delays=(2.0,)))
    translate = chain(Capability("translate", TRANSLATE_PROMPT, 4096, _ID, _ID,
                                 error=TranslationError, validate=is_french))
    summarize = chain(Capability("summarize", SUMMARY_PROMPT, _SHORT, _ID, lambda t: "",
                                 default="", validate=is_french))
    is_relevant = chain(Capability("relevance", RELEVANCE_PROMPT, _SHORT, is_yes, lambda t: False,
                                   default=True, retry_delays=(2.0,)))
    is_promotional = chain(Capability("promotion", PROMO_PROMPT, _SHORT, is_yes, lambda t: False,
                                      default=False, retry_delays=(2.0,)))
    classify = chain(Capability("hashtags", CLASSIFY_PROMPT, _SHORT, _ID, lambda t: "",
                                default="", retry_delays=(2.0,)))
    return AI(translate, summarize, is_relevant, is_promotional, is_french, classify)
