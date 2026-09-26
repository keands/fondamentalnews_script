"""Tests for full-text extraction, retweet skipping and promo filter."""

from types import SimpleNamespace

from bot.promo_filter import looks_promotional
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


def test_retweets_are_skipped():
    resp = _resp(
        [{"id": "2", "created_at": "2026-01-01T00:00:00Z", "author_id": "u1",
          "text": "RT @federalreserve: Powell: infl…",
          "referenced_tweets": [{"type": "retweeted", "id": "9"}]},
         {"id": "3", "created_at": "2026-01-01T00:00:00Z", "author_id": "u1",
          "text": "My take on this", "referenced_tweets": [{"type": "quoted", "id": "9"}]}],
        {"users": [{"id": "u1", "username": "DeItaone"}]},
    )
    assert [t.id for t, _ in _extract_tweets(resp)] == ["3"]


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
