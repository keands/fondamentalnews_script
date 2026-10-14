"""Tests for the capabilities built by build_ai (failure policies and French validation)."""

import asyncio

import pytest

from bot.ai import build_ai
from bot.translation import TranslationError


def run(coro):
    return asyncio.run(coro)


async def no_sleep(_):
    return None


def fake_provider(answers):
    """`complete` that answers by prompt kind: dict of prompt-prefix -> answer or Exception."""
    calls = []

    async def complete(prompt, max_tokens):
        calls.append(prompt)
        for key, answer in answers.items():
            if prompt.startswith(key):
                if isinstance(answer, Exception):
                    raise answer
                return answer
        raise AssertionError(f"unexpected prompt: {prompt[:40]}")

    return complete, calls


FRENCH = "Ce texte est-il rédigé"      # FRENCH_PROMPT prefix
TRANSLATE = "Traduis ce texte"         # TRANSLATE_PROMPT prefix
SUMMARY = "Résume ce tweet"            # SUMMARY_PROMPT prefix
RELEVANCE = "Does this tweet contain"  # RELEVANCE_PROMPT prefix
PROMO = "Ce tweet est-il de la promotion"


def test_no_providers_gives_empty_ai():
    ai = build_ai([])
    assert ai.translate is None and ai.is_relevant is None and ai.summarize is None


def test_translate_validated_by_french_check():
    answers = iter(["Привет", "Bonjour"])

    async def translator(prompt, max_tokens):
        if prompt.startswith(TRANSLATE):
            return next(answers)
        # French check: only the French text passes
        return "OUI" if "Bonjour" in prompt else "NON"

    ai = build_ai([("p", translator)], sleep=no_sleep)
    assert run(ai.translate("Hello")) == "Bonjour"


def test_translate_raises_when_nothing_is_valid_french():
    async def bad(prompt, max_tokens):
        return "NON" if not prompt.startswith(TRANSLATE) else "Привет"

    ai = build_ai([("p", bad)], sleep=no_sleep)
    with pytest.raises(TranslationError):
        run(ai.translate("Hello"))


def test_summarize_returns_empty_when_exhausted():
    p, _ = fake_provider({SUMMARY: RuntimeError("down")})
    ai = build_ai([("p", p)], sleep=no_sleep)
    assert run(ai.summarize("Fed hikes")) == ""


def test_relevance_fails_open_and_parses_yes_no():
    down, _ = fake_provider({RELEVANCE: RuntimeError("down")})
    assert run(build_ai([("p", down)], sleep=no_sleep).is_relevant("x")) is True
    yes, _ = fake_provider({RELEVANCE: " YES"})
    assert run(build_ai([("p", yes)], sleep=no_sleep).is_relevant("x")) is True
    no, _ = fake_provider({RELEVANCE: "NO"})
    assert run(build_ai([("p", no)], sleep=no_sleep).is_relevant("x")) is False


def test_promotion_fails_open_and_accepts_oui_or_yes():
    down, _ = fake_provider({PROMO: RuntimeError("down")})
    assert run(build_ai([("p", down)], sleep=no_sleep).is_promotional("x")) is False
    for answer in ("OUI", "YES"):
        p, _ = fake_provider({PROMO: answer})
        assert run(build_ai([("p", p)], sleep=no_sleep).is_promotional("x")) is True


def test_french_check_fails_closed():
    down, _ = fake_provider({FRENCH: RuntimeError("down")})
    assert run(build_ai([("p", down)], sleep=no_sleep).is_french("Bonjour")) is False


def test_second_provider_serves_every_capability_when_first_is_down():
    down, _ = fake_provider({k: RuntimeError("429") for k in (TRANSLATE, SUMMARY, RELEVANCE, PROMO, FRENCH)})
    up, _ = fake_provider({TRANSLATE: "Bonjour", SUMMARY: "Résumé", RELEVANCE: "YES", PROMO: "NON", FRENCH: "OUI"})
    ai = build_ai([("down", down), ("up", up)], sleep=no_sleep)
    assert run(ai.translate("Hello")) == "Bonjour"
    assert run(ai.summarize("Hello")) == "Résumé"
    assert run(ai.is_relevant("Hello")) is True
    assert run(ai.is_promotional("Hello")) is False
