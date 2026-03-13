"""Claude-powered tweet summarizer."""
import logging
import anthropic

logger = logging.getLogger(__name__)


class Summarizer:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def summarize(self, text: str) -> str:
        """Return a French summary of tweet text, preserving direct quotes."""
        if not text or not text.strip():
            return ""
        try:
            msg = await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{
                    "role": "user",
                    "content": (
                        "Analyse ce tweet en français. S'il contient une citation directe (discours rapporté), "
                        "reproduis-la mot pour mot entre guillemets. Ensuite, résume en 2 lignes : qui a dit quoi et le contexte. "
                        "Si le tweet ne contient pas de citation directe, résume-le en 3 lignes courtes et précises. "
                        "Ajoute ensuite une ligne vide, puis une section commençant par \"📊 Impact :\" expliquant en 1-2 lignes "
                        "pourquoi c'est important pour les marchés (politique monétaire, inflation, croissance, risque, etc.). "
                        "Réponds uniquement avec la sortie, sans introduction.\n\n"
                        + text
                    ),
                }],
            )
            return msg.content[0].text.strip()
        except Exception:
            logger.exception("Summarization failed")
            return text

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
