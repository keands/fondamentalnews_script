"""Claude-powered tweet relevance filter."""
import logging
import anthropic

logger = logging.getLogger(__name__)

RELEVANCE_PROMPT = (
    "Does this tweet contain a market-moving signal? "
    "A market-moving signal is actionable information such as: interest rate decisions, "
    "inflation or GDP data releases, central bank policy changes, recession warnings, "
    "earnings surprises, or breaking financial news.\n"
    "Promotional content is NEVER a market-moving signal: answer 'NO' for ads, sponsored posts, "
    "self-promotion (newsletters, courses, webinars, apps, brokers, trading signals, subscriptions), "
    "promo codes, giveaways, affiliate links or invitations to subscribe, sign up or buy.\n"
    "Respond with ONLY 'YES' or 'NO'.\n\n"
)


class Relevance:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def is_relevant(self, text: str) -> bool:
        """Return True if tweet contains a market-moving signal (promotional tweets are never relevant)."""
        if not text or not text.strip():
            return False
        try:
            msg = await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=5,
                messages=[{
                    "role": "user",
                    "content": RELEVANCE_PROMPT + text,
                }],
            )
            return msg.content[0].text.strip().upper() == "YES"
        except Exception:
            logger.exception("Relevance check failed for tweet — defaulting to relevant")
            return True
