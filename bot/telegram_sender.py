"""Send formatted messages to a Telegram channel."""

import logging

from telegram import Bot
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class TelegramSender:
    def __init__(self, token: str, channel_id: str, alert_chat_id: str = "") -> None:
        self._bot = Bot(token=token)
        self._channel_id = channel_id
        self._alert_chat_id = alert_chat_id

    async def send(self, text: str) -> None:
        """Send a Markdown-formatted message to the configured channel."""
        await self._bot.send_message(
            chat_id=self._channel_id,
            text=text + "\n\n[@fondamentalnews](https://t.me/fondamentalnews)",
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
