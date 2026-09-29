"""Tests for TranslationChain retries and provider fallback."""

import asyncio
import logging

from bot.translation import TranslationChain


def _run(coro):
    return asyncio.run(coro)


def _provider(results):
    """Return an async fn yielding results in order; exceptions are raised."""
    calls = []

    async def fn(text):
        calls.append(text)
        r = results[len(calls) - 1]
        if isinstance(r, Exception):
            raise r
        return r

    return fn, calls


def test_retries_then_succeeds_on_same_provider():
    gemini, g_calls = _provider([RuntimeError("429"), "Bonjour"])
    chain = TranslationChain([("Gemini", gemini)], retry_delays=(0, 0))
    assert _run(chain.translate("Hello")) == "Bonjour"
    assert len(g_calls) == 2


def test_falls_back_to_next_provider():
    gemini, g_calls = _provider([RuntimeError("429")] * 3)
    deepseek, d_calls = _provider(["Bonjour"])
    chain = TranslationChain([("Gemini", gemini), ("DeepSeek", deepseek)], retry_delays=(0, 0))
    assert _run(chain.translate("Hello")) == "Bonjour"
    assert len(g_calls) == 3 and len(d_calls) == 1


def test_empty_answer_counts_as_failure():
    gemini, _ = _provider(["", "  ", ""])
    deepseek, _ = _provider(["Bonjour"])
    chain = TranslationChain([("Gemini", gemini), ("DeepSeek", deepseek)], retry_delays=(0, 0))
    assert _run(chain.translate("Hello")) == "Bonjour"


def test_all_fail_returns_original_and_logs_error(caplog):
    gemini, _ = _provider([RuntimeError("down")] * 3)
    chain = TranslationChain([("Gemini", gemini)], retry_delays=(0, 0))
    with caplog.at_level(logging.INFO):
        assert _run(chain.translate("Hello")) == "Hello"
    assert any(r.levelno == logging.ERROR for r in caplog.records)
