"""Tests for FallbackChain: ordering, retries, validation, failure policy."""

import asyncio

import pytest

from bot.fallback import Capability, ChainExhausted, FallbackChain


def run(coro):
    return asyncio.run(coro)


def provider(*results):
    """Async `complete` returning/raising `results` in order; records the prompts it received."""
    calls = []

    async def complete(prompt, max_tokens):
        calls.append(prompt)
        r = results[min(len(calls), len(results)) - 1]
        if isinstance(r, Exception):
            raise r
        return r

    return complete, calls


def chain(providers, sleeps=None, **kw):
    async def sleep(seconds):
        if sleeps is not None:
            sleeps.append(seconds)

    cap = Capability("test", "PROMPT:", 10, kw.pop("parse", str), kw.pop("on_empty", lambda t: t), **kw)
    return FallbackChain(cap, providers, sleep=sleep)


def test_first_valid_provider_wins_and_receives_prompt():
    a, a_calls = provider("A")
    b, b_calls = provider("B")
    assert run(chain([("a", a), ("b", b)])("hello")) == "A"
    assert a_calls == ["PROMPT:hello"] and b_calls == []


def test_error_retries_with_pauses_then_next_provider():
    sleeps = []
    a, a_calls = provider(RuntimeError("429"))
    b, _ = provider("B")
    assert run(chain([("a", a), ("b", b)], sleeps, retry_delays=(2.0, 5.0))("x")) == "B"
    assert len(a_calls) == 3 and sleeps == [2.0, 5.0]


def test_empty_answer_counts_as_failure():
    a, _ = provider("", "  ")
    b, _ = provider("B")
    assert run(chain([("a", a), ("b", b)], retry_delays=(0.0,))("x")) == "B"


def test_invalid_answer_is_retried_without_pause_then_next_provider():
    sleeps = []

    async def valid(v):
        return v == "good"

    a, a_calls = provider("bad")
    b, _ = provider("good")
    assert run(chain([("a", a), ("b", b)], sleeps, validate=valid, retry_delays=(2.0, 5.0))("x")) == "good"
    assert len(a_calls) == 3 and sleeps == []


def test_error_after_invalid_answer_still_pauses():
    sleeps = []

    async def valid(v):
        return v == "good"

    a, _ = provider("bad", RuntimeError("down"), "good")
    assert run(chain([("a", a)], sleeps, validate=valid, retry_delays=(2.0, 5.0))("x")) == "good"
    assert sleeps == [5.0]


def test_parse_is_applied():
    a, _ = provider(" YES ")
    assert run(chain([("a", a)], parse=lambda s: s == "YES")("x")) is True


def test_all_fail_returns_default_and_logs_error(caplog):
    a, _ = provider(RuntimeError("down"))
    assert run(chain([("a", a)], default=True, retry_delays=())("x")) is True
    assert any(r.levelname == "ERROR" for r in caplog.records)


def test_all_fail_raises_without_default():
    a, _ = provider(RuntimeError("down"))
    with pytest.raises(ChainExhausted):
        run(chain([("a", a)], retry_delays=())("x"))


def test_custom_error_type():
    class MyError(Exception):
        pass

    a, _ = provider(RuntimeError("down"))
    with pytest.raises(MyError):
        run(chain([("a", a)], error=MyError, retry_delays=())("x"))


def test_blank_input_skips_providers():
    a, a_calls = provider("A")
    assert run(chain([("a", a)], on_empty=lambda t: "EMPTY")("  ")) == "EMPTY"
    assert a_calls == []


def test_no_providers_uses_failure_policy():
    assert run(chain([], default="D")("x")) == "D"
