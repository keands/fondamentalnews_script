"""Claude-powered tweet summarizer."""
import logging
import anthropic

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = (
    "Summarize this tweet in the same language as the tweet. If it contains a direct quote "
    "(reported speech), reproduce it word for word in quotation marks, then summarize in 2 lines: "
    "who said what and the context. Otherwise, summarize it in 3 short, precise lines. "
    "Then add an empty line and a section starting with \"📊 Impact:\" explaining in 1-2 lines "
    "why it matters for markets (monetary policy, inflation, growth, risk, etc.). "
    "Every sentence must be complete. Reply only with the output, no introduction.\n\n"
)


class Summarizer:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def summarize(self, text: str) -> str:
        """Return a summary of tweet text (in the tweet's language), preserving direct quotes."""
        if not text or not text.strip():
            return ""
        try:
            msg = await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": SUMMARY_PROMPT + text,
                }],
            )
            return msg.content[0].text.strip()
        except Exception:
            logger.exception("Summarization failed")
            return ""

    async def classify(self, text: str) -> str:
        """Return up to 5 French hashtags classifying the tweet topic and impacted instruments."""
        if not text or not text.strip():
            return ""
        try:
            msg = await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=50,
                messages=[{
                    "role": "user",
                    "content": (
                        "Génère 1 à 5 hashtags en FRANÇAIS pour catégoriser ce tweet financier. "
                        "Inclus : (1) l'institution/thème macro (ex: #FED #BCE #BoE #BoJ #Inflation #Taux #PIB #Emploi), "
                        "et (2) le ou les instruments financiers impactés parmi : "
                        "#Actions #Obligations #Or #Pétrole #Devises #Dollar #Euro #Crypto #Matières #Immobilier. "
                        "Réponds uniquement avec les hashtags séparés par des espaces, rien d'autre.\n\n"
                        + text
                    ),
                }],
            )
            return msg.content[0].text.strip()
        except Exception:
            logger.exception("Classification failed")
            return ""
