"""Tests for the French-script guard."""

import asyncio

from bot.language import force_french, is_french_script


def test_is_french_script():
    assert is_french_script("La BCE maintient ses taux — €, $ et 2,5 %")
    assert not is_french_script("ФРС сохранила ставку")
    assert not is_french_script("美联储维持利率不变")
    assert not is_french_script("الفيدرالي يثبت الفائدة")


def test_force_french_retries_then_returns_empty():
    answers = iter(["ФРС", "Fed"])

    async def fn(text):
        return next(answers)

    assert asyncio.run(force_french(fn)("x")) == "Fed"

    async def bad(text):
        return "美联储"

    assert asyncio.run(force_french(bad)("x")) == ""
