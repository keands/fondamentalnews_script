"""Tests for the Telegram restart button: authorization, flow, and a run against a fake Telegram API."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fake_telegram import CHAT, USER, callback_update, methods, with_fake_telegram
from bot.telegram_control import (
    CONFIRM_TEXT, PANEL_TEXT, RESTART, RESTART_CANCEL, RESTART_CONFIRM, TelegramControl,
)


def run(coro):
    return asyncio.run(coro)


def control(admin_ids=(), restarts=None):
    calls = restarts if restarts is not None else []
    return TelegramControl("123:abc", CHAT, lambda: calls.append(1), admin_ids=admin_ids), calls


def button(data, chat_id=CHAT, user_id=USER):
    query = SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock())
    update = SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(id=chat_id),
                             effective_user=SimpleNamespace(id=user_id))
    return update, query


def press(ctl, data, **kw):
    update, query = button(data, **kw)
    run(ctl._button(update, None))
    return query


def test_restart_asks_for_confirmation_without_restarting():
    ctl, restarts = control()
    query = press(ctl, RESTART)
    assert restarts == []
    assert query.edit_message_text.call_args.args[0] == CONFIRM_TEXT
    labels = [b.text for b in query.edit_message_text.call_args.kwargs["reply_markup"].inline_keyboard[0]]
    assert labels == ["✅ Confirmer", "❌ Annuler"]


def test_confirm_restarts_once_even_if_pressed_twice():
    ctl, restarts = control()
    query = press(ctl, RESTART_CONFIRM)
    press(ctl, RESTART_CONFIRM)
    assert restarts == [1]
    assert "Redémarrage" in query.edit_message_text.call_args.args[0]
    assert query.edit_message_text.call_args.kwargs["reply_markup"] is None


def test_cancel_goes_back_to_panel():
    ctl, restarts = control()
    query = press(ctl, RESTART_CANCEL)
    assert restarts == []
    assert query.edit_message_text.call_args.args[0] == PANEL_TEXT


def test_restart_still_happens_if_telegram_rejects_the_confirmation_edit():
    ctl, restarts = control()
    update, query = button(RESTART_CONFIRM)
    query.edit_message_text.side_effect = RuntimeError("network down")
    try:
        run(ctl._button(update, None))
    except RuntimeError:
        pass
    assert restarts == [1]


def test_other_chat_cannot_restart():
    ctl, restarts = control()
    query = press(ctl, RESTART_CONFIRM, chat_id=999)
    assert restarts == []
    query.edit_message_text.assert_not_called()
    query.answer.assert_called_once_with()  # spinner stopped, nothing else


def test_admin_ids_restrict_users_in_the_chat():
    ctl, restarts = control(admin_ids=[USER])
    press(ctl, RESTART_CONFIRM, user_id=1234)
    assert restarts == []
    press(ctl, RESTART_CONFIRM, user_id=USER)
    assert restarts == [1]


def test_menu_command_only_for_the_control_chat():
    ctl, _ = control()
    for chat_id, expected in ((CHAT, 1), (999, 0)):
        send = AsyncMock()
        update = SimpleNamespace(effective_chat=SimpleNamespace(id=chat_id, send_message=send),
                                 effective_user=SimpleNamespace(id=USER))
        run(ctl._menu(update, None))
        assert send.call_count == expected


# --- end to end with the real python-telegram-bot stack against a fake Telegram API ---


def test_confirm_press_restarts_and_is_acknowledged_so_it_is_not_replayed():
    async def scenario(base_url, calls):
        restart = asyncio.Event()
        ctl = TelegramControl("123:abc", CHAT, restart.set, api_base_url=base_url)
        await ctl.start()
        await asyncio.wait_for(restart.wait(), timeout=5)
        await ctl.stop()
        return calls

    calls = run(with_fake_telegram([callback_update(100, RESTART_CONFIRM)], scenario))
    assert methods(calls, "answerCallbackQuery")[0]["callback_query_id"] == "cb100"
    assert "Redémarrage en cours" in methods(calls, "editMessageText")[0]["text"]
    offsets = [int(p.get("offset", 0)) for p in methods(calls, "getUpdates")]
    assert offsets[-1] == 101  # the press (update 100) is marked as read: no restart loop
    assert methods(calls, "deleteWebhook")[0]["drop_pending_updates"] in (True, "true", "True")


def test_press_from_another_chat_is_ignored_end_to_end():
    async def scenario(base_url, calls):
        restart = asyncio.Event()
        ctl = TelegramControl("123:abc", CHAT, restart.set, api_base_url=base_url)
        await ctl.start()
        await asyncio.sleep(0.4)
        await ctl.stop()
        return restart.is_set(), calls

    restarted, calls = run(with_fake_telegram([callback_update(100, RESTART_CONFIRM, chat_id=999)], scenario))
    assert restarted is False
    assert methods(calls, "editMessageText") == []


def test_send_panel_attaches_the_restart_button():
    async def scenario(base_url, calls):
        ctl = TelegramControl("123:abc", CHAT, lambda: None, api_base_url=base_url)
        await ctl.start()
        await ctl.send_panel("✅ Bot started.")
        await ctl.stop()
        return calls

    calls = run(with_fake_telegram([], scenario))
    sent = methods(calls, "sendMessage")[0]
    assert sent["text"] == "✅ Bot started."
    assert RESTART in str(sent["reply_markup"])
