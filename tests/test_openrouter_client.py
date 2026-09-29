"""Tests for OpenRouterClient against a local fake API."""

import asyncio

from aiohttp import web

import bot.openrouter_client as ds


def _serve(answers):
    """Run a coroutine factory against a fake API returning `answers` in order."""
    requests = []

    async def handler(req):
        requests.append(await req.json())
        status, content = answers[min(len(requests), len(answers)) - 1]
        if status != 200:
            return web.Response(status=status, text="error")
        if isinstance(content, dict):
            return web.json_response(content)
        return web.json_response({"choices": [{"message": {"content": content}}]})

    async def run(coro_fn):
        app = web.Application()
        app.router.add_post("/api/v1/chat/completions", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        old = ds._API_URL
        ds._API_URL = f"http://127.0.0.1:{port}/api/v1/chat/completions"
        try:
            return await coro_fn(ds.OpenRouterClient("key", retry_delays=(0, 0)))
        finally:
            ds._API_URL = old
            await runner.cleanup()

    return run, requests


def test_summarize_retries_after_429():
    run, requests = _serve([(429, ""), (200, "Résumé")])
    assert asyncio.run(run(lambda c: c.summarize("Powell spoke"))) == "Résumé"
    assert len(requests) == 2
    assert requests[0]["model"] == "deepseek/deepseek-v4-flash"


def test_yes_no_answers():
    run, _ = _serve([(200, "YES")])
    assert asyncio.run(run(lambda c: c.is_relevant("Fed hikes"))) is True
    run, _ = _serve([(200, "OUI")])
    assert asyncio.run(run(lambda c: c.is_promotional("Use code X"))) is True


def test_failures_use_safe_defaults():
    run, requests = _serve([(500, "")])
    assert asyncio.run(run(lambda c: c.is_relevant("Fed hikes"))) is True
    assert len(requests) == 3
    run, _ = _serve([(500, "")])
    assert asyncio.run(run(lambda c: c.is_promotional("x"))) is False
    run, _ = _serve([(500, "")])
    assert asyncio.run(run(lambda c: c.classify("x"))) == ""


def test_translate_does_not_retry_itself():
    run, requests = _serve([(429, "")])
    try:
        asyncio.run(run(lambda c: c.translate("Hello")))
        raise AssertionError("expected an exception")
    except RuntimeError:
        pass
    assert len(requests) == 1


def test_error_field_in_200_response_is_retried():
    run, requests = _serve([(200, {"error": {"code": 429, "message": "rate limited"}}), (200, "Résumé")])
    assert asyncio.run(run(lambda c: c.summarize("Powell spoke"))) == "Résumé"
    assert len(requests) == 2
