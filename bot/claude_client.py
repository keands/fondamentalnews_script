"""Anthropic Claude as an AI provider (`complete`)."""

import anthropic

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class ClaudeClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, prompt: str, max_tokens: int = 1024) -> str:
        """Return the model's answer. Raises on failure."""
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
