"""Unit tests for _format_tweet conditional logic."""

from types import SimpleNamespace
from bot.tweet_monitor import _format_tweet, _MAX_TWEET_LEN, _TELEGRAM_MAX_LEN


def make_tweet(tweet_id: int = 123456789):
    return SimpleNamespace(id=tweet_id)


SHORT = "Breaking: markets up."  # well under 280 chars
LONG = "A" * (_MAX_TWEET_LEN + 1)  # 281 chars — triggers summary path
SUMMARY = "Les marchés montent fortement ce matin."
TRANSLATED = "Les marchés sont en hausse."
LABEL = "Walter Blomberg"
HANDLE = "deitaone"


def test_short_tweet_shows_original_and_translation():
    msg = _format_tweet(make_tweet(), SHORT, TRANSLATED, LABEL, HANDLE, summary=SUMMARY)
    assert SHORT in msg
    assert "🇫🇷 *Traduction:*" in msg
    assert TRANSLATED in msg
    assert f"_{SUMMARY}_" not in msg


def test_short_tweet_no_duplicate_translation():
    """When translated == original, no translation block."""
    msg = _format_tweet(make_tweet(), SHORT, SHORT, LABEL, HANDLE, summary=SUMMARY)
    assert "🇫🇷 *Traduction:*" not in msg


def test_long_tweet_shows_only_summary():
    msg = _format_tweet(make_tweet(), LONG, TRANSLATED, LABEL, HANDLE, summary=SUMMARY)
    assert f"_{SUMMARY}_" in msg
    assert LONG not in msg
    assert "🇫🇷 *Traduction:*" not in msg


def test_long_tweet_no_summary_falls_back_to_original():
    """If summarize_fn wasn't called (empty summary), show full original."""
    msg = _format_tweet(make_tweet(), LONG, TRANSLATED, LABEL, HANDLE, summary="")
    assert LONG in msg
    assert "🇫🇷 *Traduction:*" in msg


def test_header_and_link_always_present():
    tweet = make_tweet(42)
    for text, summary in [(SHORT, SUMMARY), (LONG, SUMMARY)]:
        msg = _format_tweet(tweet, text, TRANSLATED, LABEL, HANDLE, summary=summary)
        assert f"🐦 *{LABEL}* (@{HANDLE})" in msg
        assert "[Voir le tweet](https://twitter.com/deitaone/status/42)" in msg


def test_too_long_message_uses_summary_instead_of_cutting():
    huge = "B" * 4500
    msg = _format_tweet(make_tweet(), SHORT, huge, LABEL, HANDLE, summary=SUMMARY)
    assert f"_{SUMMARY}_" in msg
    assert len(msg) <= _TELEGRAM_MAX_LEN


def test_too_long_message_without_summary_keeps_full_translation():
    huge = "B" * 4500
    msg = _format_tweet(make_tweet(), "C" * 3000, huge, LABEL, HANDLE, summary="")
    assert huge in msg
    assert "C" * 3000 not in msg
