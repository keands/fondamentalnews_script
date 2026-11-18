"""Tests for OpenRouterClient.complete against a local fake API."""

import asyncio

import pytest
from aiohttp import web

import bot.openrouter_client as orc


def _serve(status=200, body=None):
    """Return (run, requests): run(coro_fn) calls coro_fn(client) against a fake API answering `body`."""
    requests = []

    async def handler(req):
        requests.append({"json": await req.json(), "auth": req.headers.get("Authorization")})
        if status != 200:
            return web.Response(status=status, text="boom")
        return web.json_response(body)

    async def run(coro_fn):
        app = web.Application()
        app.router.add_post("/api/v1/chat/completions", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        old = orc._API_URL
        orc._API_URL = f"http://127.0.0.1:{port}/api/v1/chat/completions"
        try:
            return await coro_fn(orc.OpenRouterClient("key"))
        finally:
            orc._API_URL = old
            await runner.cleanup()

    return run, requests


def answer(content):
    return {"choices": [{"message": {"content": content}}]}


def test_complete_returns_stripped_answer_and_sends_expected_request():
    run, requests = _serve(body=answer(" Bonjour \n"))
    assert asyncio.run(run(lambda c: c.complete("Dis bonjour", 77))) == "Bonjour"
    sent = requests[0]
    assert sent["auth"] == "Bearer key"
    assert sent["json"]["model"] == "deepseek/deepseek-v4-flash"
    assert sent["json"]["messages"] == [{"role": "user", "content": "Dis bonjour"}]
    assert sent["json"]["max_tokens"] == 77
    assert sent["json"]["reasoning"]["enabled"] is False


def test_http_error_raises():
    run, _ = _serve(status=429)
    with pytest.raises(RuntimeError, match="429"):
        asyncio.run(run(lambda c: c.complete("x")))


def test_error_payload_in_200_response_raises():
    run, _ = _serve(body={"error": {"code": 429, "message": "rate limited"}})
    with pytest.raises(RuntimeError, match="rate limited"):
        asyncio.run(run(lambda c: c.complete("x")))


@pytest.mark.parametrize("content", ["", "   ", None])
def test_empty_answer_raises(content):
    run, _ = _serve(body=answer(content))
    with pytest.raises(ValueError, match="empty"):
        asyncio.run(run(lambda c: c.complete("x")))
