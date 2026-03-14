"""Monitor Twitter accounts for new tweets using twscrape."""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import twscrape

logger = logging.getLogger(__name__)

_MAX_TWEET_LEN = 280

STATE_FILE = "state.json"

# Cached user IDs — populated on first lookup, never expires (IDs don't change)
_user_id_cache: dict[str, int] = {}

# Epoch timestamp until which we are rate-limited (0 = not limited)
_rate_limited_until: float = 0.0
_RATE_LIMIT_BACKOFF_SECONDS = 15 * 60  # 15 minutes


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True if the exception looks like a Twitter 429 / rate-limit error."""
    msg = str(exc).lower()
    return "rate" in msg or "429" in msg or "too many" in msg


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                return json.loads(content)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


async def check_new_tweets(
    config: dict,
    translate_fn,
    send_fn,
    state: dict,
    validate_fn=None,
    summarize_fn=None,
    classify_fn=None,
) -> None:
    """Poll each configured Twitter account and post new tweets."""
    global _rate_limited_until

    # Skip cycle if we're still in a rate-limit backoff window
    if time.time() < _rate_limited_until:
        remaining = int(_rate_limited_until - time.time())
        logger.warning("Rate-limited — skipping cycle, %d s remaining.", remaining)
        return

    twitter_cfg = config.get("twitter", {})
    accounts: list[dict[str, Any]] = twitter_cfg.get("accounts", [])

    if not accounts:
        logger.debug("No Twitter accounts configured")
        return

    api = twscrape.API()

    last_ids: dict = state.setdefault("last_tweet_ids", {})

    max_per_cycle = twitter_cfg.get("max_messages_per_cycle", 3)
    sent_count = 0

    for account in accounts:
        if sent_count >= max_per_cycle:
            logger.info("Message cap (%d) reached for this cycle, skipping remaining accounts.", max_per_cycle)
            break
        handle = account.get("handle", "")
        label = account.get("label", handle)
        if not handle:
            continue

        last_id = last_ids.get(handle)

        try:
            tweets = []
            async for tweet in api.user_tweets(await _get_user_id(api, handle), limit=20):
                if last_id and tweet.id <= int(last_id):
                    break
                tweets.append(tweet)
        except Exception as e:
            if _is_rate_limit_error(e):
                _rate_limited_until = time.time() + _RATE_LIMIT_BACKOFF_SECONDS
                logger.warning(
                    "Rate-limited by Twitter fetching @%s — pausing for %d min.",
                    handle,
                    _RATE_LIMIT_BACKOFF_SECONDS // 60,
                )
                break  # stop processing more accounts this cycle
            logger.exception("Failed to fetch tweets for @%s", handle)
            continue

        # Post newest-last so the channel reads chronologically
        for tweet in reversed(tweets):
            try:
                last_ids[handle] = str(tweet.id)  # always advance, even if skipped
                if validate_fn and not await validate_fn(tweet.rawContent):
                    logger.info("Skipped irrelevant tweet %s from @%s", tweet.id, handle)
                    continue
                if sent_count >= max_per_cycle:
                    continue
                original_text = tweet.rawContent
                translated = await translate_fn(original_text)
                summary = await summarize_fn(original_text) if summarize_fn else ""
                hashtags = await classify_fn(translated or original_text) if classify_fn else ""
                message = _format_tweet(tweet, original_text, translated, label, handle, summary, hashtags)
                await send_fn(message)
                sent_count += 1
            except Exception:
                logger.exception("Failed to process tweet %s from @%s", tweet.id, handle)


async def fetch_todays_tweets(config: dict, summarize_fn=None, validate_fn=None) -> dict[str, list[dict]]:
    """Return today's tweets (UTC) per account, optionally with AI summary."""
    global _rate_limited_until

    if time.time() < _rate_limited_until:
        remaining = int(_rate_limited_until - time.time())
        logger.warning("Rate-limited — skipping fetch_todays_tweets, %d s remaining.", remaining)
        return {}

    twitter_cfg = config.get("twitter", {})
    accounts = twitter_cfg.get("accounts", [])
    today = datetime.now(timezone.utc).date()
    api = twscrape.API()

    result: dict[str, list[dict]] = {}
    for account in accounts:
        handle = account.get("handle", "")
        label = account.get("label", handle)
        if not handle:
            continue
        tweets_today = []
        try:
            user_id = await _get_user_id(api, handle)
            async for tweet in api.user_tweets(user_id, limit=50):
                if tweet.date.date() < today:
                    break
                if tweet.date.date() == today:
                    if validate_fn and not await validate_fn(tweet.rawContent):
                        logger.info("Skipped irrelevant tweet %s from @%s", tweet.id, handle)
                        continue
                    summary = await summarize_fn(tweet.rawContent) if summarize_fn else tweet.rawContent
                    tweets_today.append({"tweet": tweet, "summary": summary, "label": label})
        except Exception as e:
            if _is_rate_limit_error(e):
                _rate_limited_until = time.time() + _RATE_LIMIT_BACKOFF_SECONDS
                logger.warning(
                    "Rate-limited by Twitter fetching @%s — pausing for %d min.",
                    handle,
                    _RATE_LIMIT_BACKOFF_SECONDS // 60,
                )
                break
            logger.exception("Failed to fetch tweets for @%s", handle)
        result[handle] = tweets_today
    return result


def _format_account_digest(handle: str, items: list[dict]) -> str:
    label = items[0]["label"]
    count = len(items)
    header = f"🐦 *{label}* (@{handle}) — {count} tweet{'s' if count > 1 else ''} aujourd'hui"
    parts = [header, ""]
    for item in items:
        t = item["tweet"]
        time_str = t.date.strftime("%H:%M")
        url = f"https://twitter.com/{handle}/status/{t.id}"
        parts.append(f"[{time_str}] {item['summary']}")
        parts.append(f"[↗]({url})")
        parts.append("")
    return "\n".join(parts).rstrip()


async def send_todays_digest(results: dict[str, list[dict]], send_fn) -> None:
    """Send one Telegram message per account that has tweets today."""
    for handle, items in results.items():
        if not items:
            continue
        message = _format_account_digest(handle, items)
        try:
            await send_fn(message)
        except Exception:
            logger.exception("Failed to send digest for @%s", handle)


async def _get_user_id(api: twscrape.API, handle: str) -> int:
    if handle in _user_id_cache:
        return _user_id_cache[handle]
    user = await api.user_by_login(handle)
    if user is None:
        raise ValueError(f"Twitter user not found: @{handle}")
    _user_id_cache[handle] = user.id
    return user.id


def _format_tweet(tweet, original: str, translated: str, label: str, handle: str, summary: str = "", hashtags: str = "") -> str:
    url = f"https://twitter.com/{handle}/status/{tweet.id}"
    parts = []
    if summary and len(original) > _MAX_TWEET_LEN:
        parts.append(f"_{summary}_")
    else:
        parts.append(original)
        if translated and translated.strip() != original.strip():
            parts += ["", "🇫🇷 *Traduction:*", translated]
    parts += ["", f"🐦 *{label}* (@{handle})", f"[Voir le tweet]({url})"]
    if hashtags:
        parts += ["", hashtags]
    return "\n".join(parts)
