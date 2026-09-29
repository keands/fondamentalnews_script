"""Translation with retries and provider fallback (DeepSeek -> Gemini -> Claude)."""

import asyncio
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

TRANSLATE_PROMPT = (
    "Traduis ce texte en français, intégralement, sans rien omettre ni résumer. "
    "Si le texte est déjà en français, retourne-le tel quel, sans explication. "
    "Réponds uniquement avec la traduction.\n\n"
)

# Seconds to wait before each retry of the same provider (429 / transient errors).
_RETRY_DELAYS = (2.0, 5.0)

TranslateFn = Callable[[str], Awaitable[str]]


class TranslationChain:
    """Try each provider in order, retrying transient failures, until one returns a translation.

    Providers raise on failure (API error, quota, empty answer). If every provider fails,
    an error is logged (forwarded to the alert chat) and the original text is returned.
    """

    def __init__(self, providers: list[tuple[str, TranslateFn]], retry_delays=_RETRY_DELAYS) -> None:
        self._providers = providers
        self._retry_delays = retry_delays

    async def translate(self, text: str) -> str:
        if not text or not text.strip():
            return text
        for name, fn in self._providers:
            for attempt, delay in enumerate((0.0, *self._retry_delays), start=1):
                if delay:
                    await asyncio.sleep(delay)
                try:
                    translated = (await fn(text) or "").strip()
                    if not translated:
                        raise ValueError("empty translation")
                    return translated
                except Exception as exc:
                    logger.info("%s translation attempt %d failed: %s: %s",
                                name, attempt, type(exc).__name__, exc)
            logger.warning("%s translation failed after %d attempts, trying next provider",
                           name, len(self._retry_delays) + 1)
        logger.error("All translation providers failed — message sent untranslated: %.100s", text)
        return text
