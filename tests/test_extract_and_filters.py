"""Tests for full-text extraction, promo filter and message splitting."""

from types import SimpleNamespace

from bot.promo_filter import looks_promotional
from bot.telegram_sender import split_message
from bot.tweet_monitor import _extract_tweets

LONG = "Powell: " + "inflation remains elevated. " * 30


def _resp(data, includes=None):
    return SimpleNamespace(data=data, includes=includes or {})


def test_long_post_uses_note_tweet_full_text():
    resp = _resp(
        {"id": "1", "created_at": "2026-01-01T00:00:00Z", "author_id": "u1",
         "text": LONG[:270] + "…", "note_tweet": {"text": LONG}},
        {"users": [{"id": "u1", "username": "DeItaone"}]},
    )
    [(tweet, handle)] = _extract_tweets(resp)
    assert tweet.rawContent == LONG
    assert handle == "DeItaone"


def test_retweet_uses_original_full_text():
    resp = _resp(
        {"id": "2", "created_at": "2026-01-01T00:00:00Z", "author_id": "u1",
         "text": "RT @federalreserve: Powell: infl…",
         "referenced_tweets": [{"type": "retweeted", "id": "9"}]},
        {"users": [{"id": "u1", "username": "DeItaone"}, {"id": "u2", "username": "federalreserve"}],
         "tweets": [{"id": "9", "author_id": "u2", "text": "short", "note_tweet": {"text": LONG}}]},
    )
    [(tweet, _)] = _extract_tweets(resp)
    assert tweet.rawContent == "RT @federalreserve: " + LONG


def test_promotional_tweets_detected():
    for text in [
        "Use code FED20 for 20% off my trading course!",
        "Rejoins mon Telegram pour mes signaux gratuits",
        "Abonnez-vous à la newsletter, lien en bio",
        "Big giveaway: win an iPhone!",
        "Great market recap tonight #ad",
    ]:
        assert looks_promotional(text), text


def test_market_news_not_flagged_as_promotional():
    for text in [
        "FED raises discount rate by 25bp",
        "BCE : réduction du bilan plus rapide que prévu",
        "US 10Y auction oversubscribed, bid-to-cover 2.6",
        "*POWELL: WE ARE PREPARED TO ADJUST POLICY",
    ]:
        assert not looks_promotional(text), text


def test_split_message_keeps_all_text():
    text = "\n".join(f"line {i} " + "x" * 90 for i in range(100))
    chunks = split_message(text, max_len=1000)
    assert all(len(c) <= 1000 for c in chunks)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")
    assert split_message("short") == ["short"]
