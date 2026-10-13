"""Claude-powered tweet summarizer."""
import logging
import anthropic

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = (
    "Résume ce tweet EN FRANÇAIS, quelle que soit la langue du tweet (jamais en russe, chinois, "
    "arabe ou autre langue). S'il contient une citation directe (propos rapportés), reproduis-la "
    "mot pour mot entre guillemets (traduite en français), puis résume en 2 lignes : qui a dit quoi "
    "et le contexte. Sinon, résume-le en 3 lignes courtes et précises. "
    "Ajoute ensuite une ligne vide et une section commençant par \"📊 Impact :\" qui explique en "
    "1-2 lignes pourquoi cela compte pour les marchés (politique monétaire, inflation, croissance, "
    "risque, etc.). Chaque phrase doit être complète. Réponds uniquement en français, "
    "sans introduction.\n\n"
)

CLASSIFY_PROMPT = (
    "Génère 1 à 5 hashtags en FRANÇAIS pour catégoriser ce tweet financier. "
    "Inclus : (1) l'institution/thème macro (ex: #FED #BCE #BoE #BoJ #Inflation #Taux #PIB #Emploi), "
    "et (2) le ou les instruments financiers impactés parmi : "
    "#Actions #Obligations #Or #Pétrole #Devises #Dollar #Euro #Crypto #Matières #Immobilier. "
    "Réponds uniquement avec les hashtags séparés par des espaces, rien d'autre.\n\n"
)


class Summarizer:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def summarize(self, text: str) -> str:
        """Return a summary of tweet text (in French), preserving direct quotes."""
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
                    "content": CLASSIFY_PROMPT + text,
                }],
            )
            return msg.content[0].text.strip()
        except Exception:
            logger.exception("Classification failed")
            return ""
