"""Telegram control panel: an inline button that restarts the bot.

The bot listens to Telegram updates (long polling) in the alert chat only. `/menu` shows a
"Restart" button; pressing it asks for a confirmation, then calls `on_restart`.
"""

import logging
import warnings
from typing import Callable, Iterable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from telegram.warnings import PTBUserWarning

logger = logging.getLogger(__name__)

RESTART = "restart"
RESTART_CONFIRM = "restart:confirm"
RESTART_CANCEL = "restart:cancel"

PANEL_TEXT = "⚙️ Contrôle du bot"
CONFIRM_TEXT = "Redémarrer le bot ? Il sera indisponible quelques secondes."


def panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Redémarrer le bot", callback_data=RESTART)]])


def confirm_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmer", callback_data=RESTART_CONFIRM),
        InlineKeyboardButton("❌ Annuler", callback_data=RESTART_CANCEL),
    ]])


class TelegramControl:
    def __init__(self, token: str, chat_id: str | int, on_restart: Callable[[], None],
                 admin_ids: Iterable[int] = (), api_base_url: str | None = None) -> None:
        """Only `chat_id` (and, when given, only the users in `admin_ids`) can use the panel.

        `on_restart` must return quickly: it only has to signal the main loop.
        `api_base_url` is for tests (a fake Telegram API).
        """
        self._chat_id = str(chat_id)
        self._admin_ids = {int(i) for i in admin_ids}
        self._on_restart = on_restart
        self._restarting = False
        builder = Application.builder().token(token).job_queue(None)  # APScheduler already runs the jobs
        if api_base_url:
            builder = builder.base_url(api_base_url)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", PTBUserWarning)  # "No JobQueue set up"
            self._app = builder.build()
        self._app.add_handler(CommandHandler("menu", self._menu))
        self._app.add_handler(CallbackQueryHandler(self._button, pattern=r"^restart(:confirm|:cancel)?$"))

    async def start(self) -> None:
        """Start listening. Updates received while the bot was down are dropped, so a stale or
        already-handled press of the button can never trigger a restart."""
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(
            allowed_updates=[Update.MESSAGE, Update.CALLBACK_QUERY], drop_pending_updates=True
        )

    async def stop(self) -> None:
        """Stop listening. Fetched updates are marked as read on Telegram's side, so the press
        that caused a restart is not delivered again to the new process."""
        if self._app.updater.running:
            await self._app.updater.stop()
        if self._app.running:
            await self._app.stop()
        await self._app.shutdown()

    async def send_panel(self, text: str = PANEL_TEXT) -> None:
        """Send `text` with the restart button to the control chat. Never raises."""
        try:
            await self._app.bot.send_message(self._chat_id, text, reply_markup=panel_markup())
        except TelegramError:
            logger.exception("Could not send the control panel")

    def _authorized(self, update: Update) -> bool:
        chat, user = update.effective_chat, update.effective_user
        if chat is None or str(chat.id) != self._chat_id:
            return False
        return not self._admin_ids or (user is not None and user.id in self._admin_ids)

    async def _menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self._authorized(update):
            await update.effective_chat.send_message(PANEL_TEXT, reply_markup=panel_markup())

    async def _button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not self._authorized(update):
            user = update.effective_user
            logger.warning("Restart button pressed by an unauthorized user (id %s)", user.id if user else "?")
            await query.answer()  # stop the spinner, do nothing else
            return

        if query.data == RESTART:
            await query.answer()
            await self._edit(query, CONFIRM_TEXT, confirm_markup())
        elif query.data == RESTART_CANCEL:
            await query.answer("Annulé")
            await self._edit(query, PANEL_TEXT, panel_markup())
        elif query.data == RESTART_CONFIRM:
            if self._restarting:
                await query.answer("Redémarrage déjà en cours")
                return
            self._restarting = True
            logger.info("Restart requested from Telegram by user %s", update.effective_user.id)
            try:
                await query.answer("Redémarrage…")
                await self._edit(query, "🔄 Redémarrage en cours…", None)
            finally:
                self._on_restart()  # restart even if Telegram did not take the confirmation

    @staticmethod
    async def _edit(query, text: str, markup: InlineKeyboardMarkup | None) -> None:
        try:
            await query.edit_message_text(text, reply_markup=markup)
        except BadRequest as exc:
            if "not modified" not in str(exc).lower():  # e.g. a double tap on the same button
                raise
