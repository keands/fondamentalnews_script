"""Claude-powered tweet summarizer."""
import logging
import anthropic

logger = logging.getLogger(__name__)


class Summarizer:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def summarize(self, text: str) -> str:
        """Return a 1-sentence French summary of tweet text."""
        if not text or not text.strip():
            return ""
        try:
            msg = await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=80,
                messages=[{
                    "role": "user",
                    "content": (
                        "Résume ce tweet en une seule phrase courte (max 15 mots) en français :\n\n"
                        + text
                    ),
                }],
            )
            return msg.content[0].text.strip()
        except Exception:
            logger.exception("Summarization failed")
            return text
