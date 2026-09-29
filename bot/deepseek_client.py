"""DeepSeek (OpenAI-compatible API) translation."""

import aiohttp

from bot.translation import TRANSLATE_PROMPT

DEFAULT_MODEL = "deepseek-v4-flash"
_API_URL = "https://api.deepseek.com/chat/completions"
_TIMEOUT = aiohttp.ClientTimeout(total=60)


class DeepSeekClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._api_key = api_key
        self._model = model or DEFAULT_MODEL

    async def translate(self, text: str) -> str:
        """Translate text to French. Raises on failure."""
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": TRANSLATE_PROMPT + text}],
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.post(_API_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"DeepSeek HTTP {resp.status}: {(await resp.text())[:200]}")
                data = await resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()
