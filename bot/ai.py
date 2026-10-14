"""The bot's AI capabilities, each a FallbackChain over the configured providers."""

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from bot.fallback import Capability, FallbackChain, Provider
from bot.language import FRENCH_PROMPT, is_yes
from bot.promo_filter import PROMO_PROMPT
from bot.relevance import RELEVANCE_PROMPT
from bot.summarizer import CLASSIFY_PROMPT, SUMMARY_PROMPT
from bot.translation import TRANSLATE_PROMPT, TranslationError

_SHORT = 1024  # even for one-word answers: reasoning tokens, if any, count against the limit
_ID = lambda s: s  # noqa: E731


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
