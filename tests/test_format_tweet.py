"""Unit tests for _format_tweet (one Telegram message per tweet)."""

from types import SimpleNamespace

from bot.tweet_monitor import _TELEGRAM_MAX_LEN, _format_tweet


def make_tweet(tweet_id: int = 123456789):
    return SimpleNamespace(id=tweet_id)


SUMMARY_FR = "Powell : la Fed reste prudente.\n\n📊 Impact : pression sur le dollar."
LABEL = "Walter Blomberg"
HANDLE = "deitaone"


def test_message_contains_translated_summary_header_and_link():
    msg = _format_tweet(make_tweet(42), SUMMARY_FR, LABEL, HANDLE, "#FED #Dollar")
    assert msg.startswith(SUMMARY_FR)
    assert f"🐦 *{LABEL}* (@{HANDLE})" in msg
    assert "[Voir le tweet](https://twitter.com/deitaone/status/42)" in msg
    assert msg.endswith("#FED #Dollar")


def test_no_hashtags_section_when_empty():
    msg = _format_tweet(make_tweet(), SUMMARY_FR, LABEL, HANDLE)
    assert msg.endswith("[Voir le tweet](https://twitter.com/deitaone/status/123456789)")


def test_oversized_text_still_fits_in_one_message():
    text = "La Fed a parlé. " * 400
    msg = _format_tweet(make_tweet(), text, LABEL, HANDLE, "#FED")
    assert len(msg) <= _TELEGRAM_MAX_LEN
    assert "…" in msg
    assert "[Voir le tweet]" in msg
