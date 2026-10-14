"""Tests for the model-based French guard."""

import asyncio

from bot.language import force_french, is_yes


def test_is_yes():
    assert is_yes("OUI") and is_yes("'oui'.") and is_yes("**YES**")
    assert not is_yes("NON")


def test_force_french_retries_then_returns_empty():
    answers = iter(["ФРС", "Fed"])

    async def fn(text):
        return next(answers)

    async def check(text):
        return text == "Fed"

    assert asyncio.run(force_french(fn, check)("x")) == "Fed"

    async def bad(text):
        return "美联储"

    assert asyncio.run(force_french(bad, check)("x")) == ""
