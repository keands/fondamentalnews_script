"""OpenRouter (OpenAI-compatible API, default model DeepSeek V4 Flash): translation, summary,
relevance, promotion check, hashtags."""

import asyncio
import logging

import aiohttp

from bot.promo_filter import PROMO_PROMPT
from bot.relevance import RELEVANCE_PROMPT
from bot.summarizer import CLASSIFY_PROMPT, SUMMARY_PROMPT
from bot.translation import TRANSLATE_PROMPT

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = aiohttp.ClientTimeout(total=60)
# Seconds to wait before each retry (429 / transient errors / empty answer).
_RETRY_DELAYS = (2.0, 5.0)


class OpenRouterClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, retry_delays=_RETRY_DELAYS) -> None:
        self._api_key = api_key
        self._model = model or DEFAULT_MODEL
        self._retry_delays = retry_delays

    async def _request(self, prompt: str, max_tokens: int) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.post(_API_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"OpenRouter HTTP {resp.status}: {(await resp.text())[:200]}")
                data = await resp.json()
        if "error" in data:
            raise RuntimeError(f"OpenRouter error: {str(data['error'])[:200]}")
        answer = (data["choices"][0]["message"]["content"] or "").strip()
        if not answer:
            raise ValueError("OpenRouter returned an empty answer")
        return answer

    async def _chat(self, prompt: str, max_tokens: int = 1024) -> str:
        """Send one prompt, retrying transient failures. Raises after the last attempt."""
        for attempt, delay in enumerate((0.0, *self._retry_delays), start=1):
            if delay:
                await asyncio.sleep(delay)
            try:
                return await self._request(prompt, max_tokens)
            except Exception as exc:
                if attempt > len(self._retry_delays):
                    raise
                logger.info("OpenRouter attempt %d failed: %s: %s", attempt, type(exc).__name__, exc)

    async def translate(self, text: str) -> str:
        """Translate text to French. Raises on failure; TranslationChain handles the retries."""
        return await self._request(TRANSLATE_PROMPT + text, max_tokens=4096)

    async def summarize(self, text: str) -> str:
        """Return a summary of tweet text (in the tweet's language). Returns "" on failure."""
        if not text or not text.strip():
            return ""
        try:
            return await self._chat(SUMMARY_PROMPT + text)
        except Exception:
            logger.exception("OpenRouter summarization failed")
            return ""

    async def is_relevant(self, text: str) -> bool:
        """Return True if tweet contains a market-moving signal. Defaults to True on failure."""
        if not text or not text.strip():
            return False
        try:
            return (await self._chat(RELEVANCE_PROMPT + text, max_tokens=10)).upper().startswith("YES")
        except Exception:
            logger.exception("OpenRouter relevance check failed — defaulting to relevant")
            return True

    async def is_promotional(self, text: str) -> bool:
        """Return True if the tweet is promotional content. Defaults to False on failure."""
        if not text or not text.strip():
            return False
        try:
            return (await self._chat(PROMO_PROMPT + text, max_tokens=10)).upper().startswith("OUI")
        except Exception:
            logger.exception("OpenRouter promotion check failed — defaulting to not promotional")
            return False

    async def classify(self, text: str) -> str:
        """Return up to 5 French hashtags for the tweet. Returns "" on failure."""
        if not text or not text.strip():
            return ""
        try:
            return await self._chat(CLASSIFY_PROMPT + text, max_tokens=100)
        except Exception:
            logger.exception("OpenRouter classification failed")
            return ""
