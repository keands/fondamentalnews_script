"""End to end: pressing "Confirmer" makes main() clean up and ask for a process restart."""

import asyncio
import logging

import pytest

import main as app
from bot.telegram_control import RESTART_CONFIRM, TelegramControl
from fake_telegram import CHAT, callback_update, methods, with_fake_telegram


class StubSender:
    def __init__(self, **kwargs):
        self.sent, self.alerts = [], []

    async def send(self, text):
        self.sent.append(text)

    async def send_alert(self, text):
        self.alerts.append(text)


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # state.json is written to the working directory
    root = logging.getLogger()
    handlers = list(root.handlers)
    yield
    root.handlers[:] = handlers  # drop the alert handler main() installs


def test_confirm_press_stops_everything_cleanly_and_requests_a_restart(monkeypatch, clean_env):
    stub = StubSender()
    events = {"stream_cancelled": False}

    async def fake_stream(**kwargs):
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            events["stream_cancelled"] = True
            raise

    async def no_job(**kwargs):
        return None

    monkeypatch.setattr(app, "TelegramSender", lambda **kw: stub)
    monkeypatch.setattr(app, "consume_stream", fake_stream)
    monkeypatch.setattr(app, "morning_digest", no_job)
    monkeypatch.setattr(app, "check_releases", no_job)
    monkeypatch.setattr(app, "load_config", lambda: {
        "telegram": {"token": "123:abc", "channel_id": "@c", "alert_chat_id": CHAT},
    })

    async def scenario(base_url, calls):
        monkeypatch.setattr(app, "TelegramControl",
                            lambda **kw: TelegramControl(api_base_url=base_url, **kw))
        restart_requested = await asyncio.wait_for(app.main(), timeout=20)
        return restart_requested, calls

    restart_requested, calls = asyncio.run(
        with_fake_telegram([callback_update(100, RESTART_CONFIRM)], scenario))

    assert restart_requested is True
    assert events["stream_cancelled"] is True
    assert "🛑 Bot stopped." not in stub.alerts            # a restart is not a shutdown notice
    assert "✅ Bot started." in methods(calls, "sendMessage")[0]["text"]  # panel with the button
    assert "Redémarrage en cours" in methods(calls, "editMessageText")[0]["text"]


def test_sigterm_stops_cleanly_saves_state_and_says_so(monkeypatch, clean_env):
    """`systemctl stop/restart` sends SIGTERM: the state must be saved before exiting."""
    import json
    import os
    import signal
    from pathlib import Path

    stub = StubSender()

    async def fake_stream(**kwargs):
        await asyncio.sleep(3600)

    async def no_job(**kwargs):
        return None

    monkeypatch.setattr(app, "TelegramSender", lambda **kw: stub)
    monkeypatch.setattr(app, "consume_stream", fake_stream)
    monkeypatch.setattr(app, "morning_digest", no_job)
    monkeypatch.setattr(app, "check_releases", no_job)
    monkeypatch.setattr(app, "load_config", lambda: {
        "telegram": {"token": "123:abc", "channel_id": "@c"},  # no alert chat: no control panel
    })

    async def run_and_terminate():
        loop = asyncio.get_running_loop()
        # State changed in memory after the last periodic save: only a clean stop persists it.
        monkeypatch.setattr(app, "load_state", lambda: {"last_digest_date": "2026-01-02"})
        loop.call_later(0.5, os.kill, os.getpid(), signal.SIGTERM)
        return await asyncio.wait_for(app.main(), timeout=20)

    restart_requested = asyncio.run(run_and_terminate())

    assert restart_requested is False
    assert "🛑 Bot stopped." in stub.alerts
    assert json.loads(Path("state.json").read_text())["last_digest_date"] == "2026-01-02"
