"""Logging handler forwarding warnings and errors to the Telegram alert chat."""

import asyncio
import logging
import time
import traceback
from typing import Awaitable, Callable

# Telegram caps messages at 4096 characters.
_MAX_LEN = 4000
_ICONS = {logging.WARNING: "⚠️", logging.ERROR: "❌", logging.CRITICAL: "🔥"}


class TelegramAlertHandler(logging.Handler):
    """Send every log record at `level` or above to the alert chat.

    Thread-safe (the X stream logs from a background thread) and throttled:
    the same message (logger + template) is sent at most once per `cooldown`
    seconds; repeats in between are counted and reported with the next one.
    """

    def __init__(
        self,
        send_alert: Callable[[str], Awaitable[None]],
        loop: asyncio.AbstractEventLoop,
        level: int = logging.WARNING,
        cooldown: float = 60.0,
    ) -> None:
        super().__init__(level)
        self._send_alert = send_alert
        self._loop = loop
        self._cooldown = cooldown
        self._last_sent: dict[tuple[str, str], float] = {}
        self._suppressed: dict[tuple[str, str], int] = {}
        # Failures while sending an alert must not trigger another alert.
        self.addFilter(lambda r: r.name != "bot.telegram_sender")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            key = (record.name, str(record.msg))
            now = time.monotonic()
            with self.lock:
                last = self._last_sent.get(key)
                if last is not None and now - last < self._cooldown:
                    self._suppressed[key] = self._suppressed.get(key, 0) + 1
                    return
                self._last_sent[key] = now
                repeated = self._suppressed.pop(key, 0)

            text = self._format(record, repeated)
            if self._loop.is_closed():
                return
            self._loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._send_alert(text))
            )
        except Exception:
            self.handleError(record)

    @staticmethod
    def _format(record: logging.LogRecord, repeated: int) -> str:
        icon = _ICONS.get(record.levelno, "⚠️")
        lines = [f"{icon} {record.levelname} — {record.name}", record.getMessage()]
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            lines.append(f"{type(exc).__name__}: {exc}")
            tb = traceback.extract_tb(record.exc_info[2])
            if tb:
                frame = tb[-1]
                lines.append(f"at {frame.filename}:{frame.lineno} in {frame.name}")
        if repeated:
            lines.append(f"(+{repeated} identical since last alert)")
        text = "\n".join(lines)
        return text if len(text) <= _MAX_LEN else text[:_MAX_LEN] + "…"
