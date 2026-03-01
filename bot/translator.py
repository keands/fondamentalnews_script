"""Claude-powered translation wrapper."""

import logging

import anthropic

logger = logging.getLogger(__name__)


class Translator:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def translate(self, text: str, target_lang: str = "FR") -> str:
        """Translate text to French. Returns original text on failure."""
        if not text or not text.strip():
            return text
        try:
            msg = await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": (
                        "Traduis ce texte en français. Si le texte est déjà en français, "
                        "retourne-le tel quel, sans explication. Réponds uniquement avec la traduction.\n\n"
                        + text
                    ),
                }],
            )
            return msg.content[0].text.strip()
        except Exception:
            logger.exception("Translation failed, returning original text")
            return text
