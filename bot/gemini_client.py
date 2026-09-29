"""Google Gemini-powered translation, summary and promotion detection."""

import logging

from google import genai

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

    async def translate(self, text: str) -> str:
        """Translate text to French. Raises on failure (handled by TranslationChain)."""
        return await self._generate(TRANSLATE_PROMPT + text)

    async def summarize(self, text: str) -> str:
        """Return a summary of tweet text (in the tweet's language). Returns "" on failure."""
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
            return answer.upper().startswith("OUI")
        except Exception:
            logger.exception("Gemini promotion check failed — defaulting to not promotional")
            return False
