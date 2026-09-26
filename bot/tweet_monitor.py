"""Monitor X accounts for new posts via the official X API filtered stream."""

import asyncio
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import xdk

from bot.promo_filter import looks_promotional

logger = logging.getLogger(__name__)

_MAX_TWEET_LEN = 280
# Telegram caps messages at 4096 chars; keep room for the channel footer added by the sender.
_TELEGRAM_MAX_LEN = 4000

STATE_FILE = "state.json"

_STREAM_RULE_TAG = "fondamentalnews-accounts"
_DEDUPE_SIZE = 500


@dataclass(frozen=True)
class Tweet:
    id: str
    rawContent: str
    date: datetime


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


def _sync_rules(client: xdk.Client, handles: list[str]) -> None:
    """Replace the stream's rule set with a single rule covering all configured handles."""
    rule_value = " OR ".join(f"from:{h}" for h in handles)
    client.stream.update_rules(body={}, delete_all=True)
    client.stream.update_rules(body={"add": [{"value": rule_value, "tag": _STREAM_RULE_TAG}]})
    logger.info("Synced X stream rule: %s", rule_value)


def _make_stream_config() -> xdk.StreamConfig:
    return xdk.StreamConfig(
        max_retries=-1,  # rely on the SDK's built-in exponential-backoff reconnect
        initial_backoff=1.0,
        max_backoff=60.0,
        on_connect=lambda: logger.info("Connected to X filtered stream."),
        on_disconnect=lambda exc: logger.warning("X stream disconnected: %s", exc),
        on_reconnect=lambda attempt, delay: logger.info(
            "Reconnecting to X stream (attempt %d) in %.1fs", attempt, delay
        ),
        on_error=lambda err: logger.warning("X stream error: %s", err),
    )


def _stream_worker(
    client: xdk.Client,
    loop: asyncio.AbstractEventLoop,
    out_queue: "asyncio.Queue",
    stop_event: threading.Event,
) -> None:
    """Runs in a background thread — client.stream.posts() is a blocking generator."""
    try:
        for resp in client.stream.posts(
            # note_tweet carries the full text of long posts (>280 chars), which "text" truncates;
            # referenced_tweets lets us recover the full original text of retweets.
            tweet_fields=["created_at", "note_tweet", "referenced_tweets"],
            expansions=["author_id", "referenced_tweets.id", "referenced_tweets.id.author_id"],
            user_fields=["username"],
            stream_config=_make_stream_config(),
        ):
            if stop_event.is_set():
                break
            loop.call_soon_threadsafe(out_queue.put_nowait, resp)
    except Exception:
        logger.exception("X stream worker terminated (non-retryable error).")
    finally:
        loop.call_soon_threadsafe(out_queue.put_nowait, None)  # sentinel: stream ended


def _full_text(item: dict) -> str:
    """Return the untruncated text of a tweet payload (long posts store it in note_tweet)."""
    note = item.get("note_tweet") or {}
    return note.get("text") or item.get("text", "")


def _tweet_text(item: dict, tweets_by_id: dict, users_by_id: dict) -> str:
    """Return the full text of a tweet, resolving retweets (whose "text" is truncated) to the original."""
    for ref in item.get("referenced_tweets") or []:
        if ref.get("type") != "retweeted":
            continue
        original = tweets_by_id.get(ref.get("id"))
        if original:
            author = users_by_id.get(original.get("author_id"), "")
            prefix = f"RT @{author}: " if author else ""
            return prefix + _full_text(original)
    return _full_text(item)


def _extract_tweets(resp: Any) -> list[tuple[Tweet, str]]:
    """Return [(Tweet, handle), ...] for one streamed response."""
    data = resp.data
    if not data:
        return []
    items = data if isinstance(data, list) else [data]

    includes = resp.includes or {}
    users_by_id = {u.get("id"): u.get("username", "") for u in includes.get("users", [])}
    tweets_by_id = {t.get("id"): t for t in includes.get("tweets", [])}

    results = []
    for item in items:
        tweet_id = item.get("id")
        created_at = item.get("created_at")
        if not tweet_id or not created_at:
            continue
        date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        handle = users_by_id.get(item.get("author_id"), "")
        results.append((Tweet(id=str(tweet_id), rawContent=_tweet_text(item, tweets_by_id, users_by_id), date=date), handle))
    return results


def _allow_send(recent_sends: deque, max_per_window: int, window_seconds: float) -> bool:
    now = time.time()
    cutoff = now - window_seconds
    while recent_sends and recent_sends[0] < cutoff:
        recent_sends.popleft()
    if len(recent_sends) >= max_per_window:
        return False
    recent_sends.append(now)
    return True


async def consume_stream(
    config: dict,
    translate_fn,
    send_fn,
    state: dict,
    validate_fn=None,
    summarize_fn=None,
    classify_fn=None,
    promo_fn=None,
) -> None:
    """Consume the X filtered stream and post new tweets to Telegram.

    Runs forever until cancelled — intended to be started once as a background
    asyncio task (not scheduled on an interval).
    """
    twitter_cfg = config.get("twitter", {})
    accounts: list[dict[str, Any]] = twitter_cfg.get("accounts", [])
    bearer_token = twitter_cfg.get("bearer_token", "")

    if not accounts:
        logger.warning("No Twitter accounts configured — stream not started.")
        return
    if not bearer_token:
        logger.warning("No twitter.bearer_token configured — stream not started.")
        return

    handle_label = {
        a["handle"].lower(): a.get("label", a["handle"]) for a in accounts if a.get("handle")
    }
    client = xdk.Client(bearer_token=bearer_token)
    _sync_rules(client, list(handle_label))

    last_ids: dict = state.setdefault("last_tweet_ids", {})
    seen_ids: deque = deque(maxlen=_DEDUPE_SIZE)
    recent_sends: deque = deque()
    max_per_window = twitter_cfg.get("max_messages_per_window", 3)
    window_minutes = twitter_cfg.get("window_minutes", 5)

    loop = asyncio.get_running_loop()
    out_queue: asyncio.Queue = asyncio.Queue()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_stream_worker,
        args=(client, loop, out_queue, stop_event),
        daemon=True,
        name="x-stream-worker",
    )
    thread.start()

    try:
        while True:
            resp = await out_queue.get()
            if resp is None:
                raise RuntimeError("X stream worker exited — tweets will no longer be received.")

            for tweet, handle in _extract_tweets(resp):
                if not handle or handle.lower() not in handle_label:
                    logger.info(
                        "Received tweet %s from unconfigured/unmatched handle @%s — dropping.",
                        tweet.id, handle,
                    )
                    continue
                handle = handle.lower()
                if tweet.id in seen_ids:
                    continue
                seen_ids.append(tweet.id)
                last_ids[handle] = tweet.id
                label = handle_label[handle]

                try:
                    if looks_promotional(tweet.rawContent) or (
                        promo_fn and await promo_fn(tweet.rawContent)
                    ):
                        logger.info("Skipped promotional tweet %s from @%s", tweet.id, handle)
                        continue
                    if validate_fn and not await validate_fn(tweet.rawContent):
                        logger.info("Skipped irrelevant tweet %s from @%s", tweet.id, handle)
                        continue
                    if not _allow_send(recent_sends, max_per_window, window_minutes * 60):
                        logger.info("Rate limit reached, dropping tweet %s from @%s", tweet.id, handle)
                        continue
                    original_text = tweet.rawContent
                    translated = await translate_fn(original_text) if translate_fn else ""
                    summary = await summarize_fn(original_text) if summarize_fn else ""
                    hashtags = await classify_fn(translated or original_text) if classify_fn else ""
                    message = _format_tweet(tweet, original_text, translated, label, handle, summary, hashtags)
                    await send_fn(message)
                except Exception:
                    logger.exception("Failed to process tweet %s from @%s", tweet.id, handle)
    finally:
        stop_event.set()


def _format_tweet(tweet, original: str, translated: str, label: str, handle: str, summary: str = "", hashtags: str = "") -> str:
    """Build the Telegram message. Text is never cut: when the full tweet doesn't fit
    in one Telegram message, the summary (or the French translation alone) is used instead."""
    url = f"https://twitter.com/{handle}/status/{tweet.id}"
    footer = ["", f"🐦 *{label}* (@{handle})", f"[Voir le tweet]({url})"]
    if hashtags:
        footer += ["", hashtags]

    if not (summary and len(original) > _MAX_TWEET_LEN):
        body = [original]
        if translated and translated.strip() != original.strip():
            body += ["", "🇫🇷 *Traduction:*", translated]
        message = "\n".join(body + footer)
        if len(message) <= _TELEGRAM_MAX_LEN:
            return message
        if not summary:
            # No summary available: keep only the French version rather than cutting the text.
            return "\n".join([translated or original] + footer)
    return "\n".join([f"_{summary}_"] + footer)
