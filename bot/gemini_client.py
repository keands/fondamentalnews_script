"""Google Gemini-powered translation, summary and promotion detection."""

import logging

from google import genai

from bot.language import FRENCH_PROMPT, is_yes
from bot.promo_filter import PROMO_PROMPT
from bot.summarizer import SUMMARY_PROMPT
from bot.translation import TRANSLATE_PROMPT

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-flash-latest"


class GeminiClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or DEFAULT_MODEL

    async def _generate(self, prompt: str) -> str:
        resp = await self._client.aio.models.generate_content(model=self._model, contents=prompt)
        return (resp.text or "").strip()

    async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        """Provider primitive for bot.fallback: one attempt, raises on failure (max_tokens unused)."""
        return await self._generate(prompt)

    async def translate(self, text: str) -> str:
        """Translate text to French. Raises on failure (handled by TranslationChain)."""
        return await self._generate(TRANSLATE_PROMPT + text)

    async def summarize(self, text: str) -> str:
        """Return a summary of tweet text (in French). Returns "" on failure."""
        if not text or not text.strip():
            return ""
        try:
            return await self._generate(SUMMARY_PROMPT + text)
        except Exception:
            logger.exception("Gemini summarization failed")
            return ""

    async def is_promotional(self, text: str) -> bool:
        """Return True if the tweet is promotional/advertising content."""
        if not text or not text.strip():
            return False
        try:
            answer = await self._generate(PROMO_PROMPT + text)
            return answer.upper().startswith(("OUI", "YES"))
        except Exception:
            logger.exception("Gemini promotion check failed — defaulting to not promotional")
            return False

    async def is_french(self, text: str) -> bool:
        """Return True if the text is written in French. Fails closed (False) on error."""
        try:
            return is_yes(await self._generate(FRENCH_PROMPT + text))
        except Exception:
            logger.exception("Gemini language check failed — treating as not French")
            return False
