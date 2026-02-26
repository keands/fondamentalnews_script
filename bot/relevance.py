"""Claude-powered tweet relevance filter."""
import logging
import anthropic

logger = logging.getLogger(__name__)


class Relevance:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def is_relevant(self, text: str) -> bool:
        """Return True if tweet contains a market-moving signal."""
        if not text or not text.strip():
            return False
        try:
            msg = await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=5,
                messages=[{
                    "role": "user",
                    "content": (
                        "Does this tweet contain a market-moving signal? "
                        "A market-moving signal is actionable information such as: interest rate decisions, "
                        "inflation or GDP data releases, central bank policy changes, recession warnings, "
                        "earnings surprises, or breaking financial news.\n"
                        "Respond with ONLY 'YES' or 'NO'.\n\n"
                        + text
                    ),
                }],
            )
            return msg.content[0].text.strip().upper() == "YES"
        except Exception:
            logger.exception("Relevance check failed for tweet — defaulting to relevant")
            return True
