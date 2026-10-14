"""Chain of responsibility over AI providers.

A *capability* (translate, summarize, relevance check...) is defined once: a prompt, how to parse the
answer, how to validate it and what to do when nothing works. A `FallbackChain` runs it against an
ordered list of providers: each one gets its retries, and the first valid answer wins. Providers only
have to expose `complete(prompt, max_tokens)` and raise on failure; the failure policy lives here.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

CompleteFn = Callable[[str, int], Awaitable[str]]
Provider = tuple[str, CompleteFn]

_RAISE = object()   # default: raise instead of returning a fallback value
_FAILED = object()  # internal: provider gave no valid answer


class ChainExhausted(Exception):
    """Every provider failed (or gave an invalid answer) for a capability."""


@dataclass(frozen=True)
class Capability(Generic[T]):
    name: str
    prompt: str                                    # prepended to the input text
    max_tokens: int
    parse: Callable[[str], T]
    on_empty: Callable[[str], T]                   # result for blank input (no provider call)
    default: Any = _RAISE                          # result when every provider fails; _RAISE = raise
    error: type[Exception] = ChainExhausted        # raised when default is _RAISE
    validate: Callable[[T], Awaitable[bool]] | None = None
    retry_delays: tuple[float, ...] = (2.0, 5.0)   # pauses before each retry of one provider


class FallbackChain(Generic[T]):
    def __init__(self, capability: Capability[T], providers: list[Provider],
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.capability = capability
        self._providers = providers
        self._sleep = sleep

    async def __call__(self, text: str) -> T:
        cap = self.capability
        if not text or not text.strip():
            return cap.on_empty(text)
        prompt = cap.prompt + text
        for name, complete in self._providers:
            result = await self._try_provider(name, complete, prompt)
            if result is not _FAILED:
                return result
            logger.warning("%s: %s gave no valid answer, trying next provider", cap.name, name)
        return self._exhausted(text)

    async def _try_provider(self, name: str, complete: CompleteFn, prompt: str) -> Any:
        cap = self.capability
        pause = 0.0
        for attempt in range(1, len(cap.retry_delays) + 2):
            if pause:
                await self._sleep(pause)
            # Pause only after an error (rate limit, outage); an invalid answer is retried at once.
            pause = cap.retry_delays[attempt - 1] if attempt <= len(cap.retry_delays) else 0.0
            try:
                answer = (await complete(prompt, cap.max_tokens) or "").strip()
                if not answer:
                    raise ValueError("empty answer")
                value = cap.parse(answer)
                if cap.validate and not await cap.validate(value):
                    logger.info("%s: %s attempt %d: invalid answer: %.80s", cap.name, name, attempt, answer)
                    pause = 0.0
                    continue
                return value
            except Exception as exc:
                logger.info("%s: %s attempt %d failed: %s: %s",
                            cap.name, name, attempt, type(exc).__name__, exc)
        return _FAILED

    def _exhausted(self, text: str) -> T:
        cap = self.capability
        if cap.default is _RAISE:
            logger.error("%s: all providers failed — input dropped: %.100s", cap.name, text)
            raise cap.error(f"{cap.name}: all providers failed")
        logger.error("%s: all providers failed — using default %r", cap.name, cap.default)
        return cap.default
