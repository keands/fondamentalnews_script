"""OpenRouter (OpenAI-compatible API, default model DeepSeek V4 Flash) as an AI provider."""

import aiohttp

DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = aiohttp.ClientTimeout(total=60)


class OpenRouterClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._api_key = api_key
        self._model = model or DEFAULT_MODEL

    async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        """One attempt; raises on HTTP error, error payload or empty answer (retries: bot.fallback)."""
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            # DeepSeek V4 Flash reasons before answering by default; that is not needed here
            # and reasoning tokens count against max_tokens.
            "reasoning": {"enabled": False, "exclude": True},
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
