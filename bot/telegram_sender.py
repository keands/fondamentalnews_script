"""Send formatted messages to a Telegram channel."""

import logging

from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

_TELEGRAM_MAX_LEN = 4096


def split_message(text: str, max_len: int = _TELEGRAM_MAX_LEN) -> list[str]:
    """Split text into chunks of at most max_len chars, preferring line then word boundaries."""
    chunks = []
    while len(text) > max_len:
        cut = text.rfind("\n", 0, max_len)
        if cut <= 0:
            cut = text.rfind(" ", 0, max_len)
        if cut <= 0:
            cut = max_len
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        chunks.append(text)
    return chunks


class TelegramSender:
    def __init__(self, token: str, channel_id: str, alert_chat_id: str = "") -> None:
        self._bot = Bot(token=token)
        self._channel_id = channel_id
        self._alert_chat_id = alert_chat_id

    async def send(self, text: str) -> None:
        """Send a Markdown-formatted message to the configured channel.

        Messages longer than Telegram's limit are split into several messages
        instead of being truncated.
        """
        for chunk in split_message(text + "\n\n[@fondamentalnews](https://t.me/fondamentalnews)"):
            await self._bot.send_message(
                chat_id=self._channel_id,
                text=chunk,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )

    async def send_alert(self, text: str) -> None:
        """Send a plain-text alert to the owner's personal chat."""
        if not self._alert_chat_id:
            return
        try:
            await self._bot.send_message(
                chat_id=self._alert_chat_id,
                text=text,
            )
        except Exception:
            logger.exception("Failed to send alert DM")

    async def send_v2(self, text: str) -> None:
        """Send a MarkdownV2-formatted message."""
        await self._bot.send_message(
            chat_id=self._channel_id,
            text=text + "\n\n[@fondamentalnews](https://t\\.me/fondamentalnews)",
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )
