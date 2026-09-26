"""Google Gemini-powered translation, summary and promotion detection."""

import logging

from google import genai

from bot.summarizer import SUMMARY_PROMPT

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-flash-latest"


class GeminiClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or DEFAULT_MODEL

    async def _generate(self, prompt: str) -> str:
        resp = await self._client.aio.models.generate_content(model=self._model, contents=prompt)
        return (resp.text or "").strip()

    async def translate(self, text: str, target_lang: str = "FR") -> str:
        """Translate text to French. Returns original text on failure."""
        if not text or not text.strip():
            return text
        try:
            translated = await self._generate(
                "Traduis ce texte en français, intégralement, sans rien omettre ni résumer. "
                "Si le texte est déjà en français, retourne-le tel quel, sans explication. "
                "Réponds uniquement avec la traduction.\n\n"
                + text
            )
            return translated or text
        except Exception:
            logger.exception("Gemini translation failed, returning original text")
            return text

    async def summarize(self, text: str) -> str:
        """Return a French summary of tweet text. Returns original text on failure."""
        if not text or not text.strip():
            return ""
        try:
            return await self._generate(SUMMARY_PROMPT + text) or text
        except Exception:
            logger.exception("Gemini summarization failed")
            return text

    async def is_promotional(self, text: str) -> bool:
        """Return True if the tweet is promotional/advertising content."""
        if not text or not text.strip():
            return False
        try:
            answer = await self._generate(
                "Ce tweet est-il de la promotion ou de la publicité ? C'est le cas s'il fait la "
                "promotion d'un produit, service, abonnement, newsletter, formation, webinaire, "
                "application, broker, code promo, concours/giveaway, lien d'affiliation, ou s'il "
                "invite à s'abonner, s'inscrire ou acheter. Une information de marché ou une actualité "
                "n'est PAS de la promotion.\n"
                "Réponds uniquement par 'OUI' ou 'NON'.\n\n"
                + text
            )
            return answer.upper().startswith("OUI")
        except Exception:
            logger.exception("Gemini promotion check failed — defaulting to not promotional")
            return False
