"""Google Gemini as an AI provider."""

from google import genai

DEFAULT_MODEL = "gemini-flash-latest"


class GeminiClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or DEFAULT_MODEL

    async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        """One attempt; raises on API error (retries: bot.fallback). max_tokens is not enforced."""
        resp = await self._client.aio.models.generate_content(model=self._model, contents=prompt)
        return (resp.text or "").strip()
