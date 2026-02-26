"""DeepL translation wrapper."""

import logging

import deepl

logger = logging.getLogger(__name__)


class Translator:
    def __init__(self, api_key: str) -> None:
        self._client = deepl.Translator(api_key)

    async def translate(self, text: str, target_lang: str = "FR") -> str:
        """Translate text to target_lang. Returns original text on failure."""
        if not text or not text.strip():
            return text
        try:
            result = self._client.translate_text(text, target_lang=target_lang)
            # Skip if DeepL detected source as already the target language
            if result.detected_source_lang.upper() == target_lang.upper():
                return text
            return result.text
        except Exception:
            logger.exception("Translation failed, returning original text")
            return text
