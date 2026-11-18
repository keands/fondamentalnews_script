"""A fake Telegram Bot API (aiohttp) to run the real python-telegram-bot stack in tests."""

import asyncio

from aiohttp import web

CHAT = 42
USER = 7


def callback_update(update_id, data, chat_id=CHAT, user_id=USER):
    user = {"id": user_id, "is_bot": False, "first_name": "K"}
    return {"update_id": update_id, "callback_query": {
        "id": f"cb{update_id}", "from": user, "chat_instance": "x", "data": data,
        "message": {"message_id": 5, "date": 0, "chat": {"id": chat_id, "type": "private"},
                    "from": {"id": 1, "is_bot": True, "first_name": "bot"}, "text": "panel"},
    }}


async def with_fake_telegram(updates, scenario):
    """Serve `updates` once on getUpdates, record every API call, then run scenario(base_url, calls)."""
    calls = []
    pending = list(updates)

    async def handler(request):
        method = request.match_info["method"]
        try:
            params = await request.json()
        except Exception:
            params = dict(await request.post())
        calls.append((method, params))
        if method == "getMe":
            result = {"id": 1, "is_bot": True, "first_name": "bot", "username": "bot"}
        elif method == "getUpdates":
            result, pending[:] = list(pending), []
            if not result:
                await asyncio.sleep(0.05)
        elif method == "sendMessage":
            result = {"message_id": 9, "date": 0, "chat": {"id": CHAT, "type": "private"}, "text": "x"}
        else:  # deleteWebhook, answerCallbackQuery, editMessageText
            result = True
        return web.json_response({"ok": True, "result": result})

    app = web.Application()
    app.router.add_post("/bot{token}/{method}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        return await scenario(f"http://127.0.0.1:{port}/bot", calls)
    finally:
        await runner.cleanup()


def methods(calls, name):
    return [params for method, params in calls if method == name]
