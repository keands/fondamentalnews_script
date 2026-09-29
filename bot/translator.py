"""Claude-powered translation wrapper."""

import anthropic

from bot.translation import TRANSLATE_PROMPT


class Translator:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def translate(self, text: str) -> str:
        """Translate text to French. Raises on failure (handled by TranslationChain)."""
        msg = await self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": TRANSLATE_PROMPT + text}],
        )
        return msg.content[0].text.strip()
