"""fondamentalnewsbot — Entry point.

Starts the APScheduler for scheduled jobs and a background X (Twitter)
filtered-stream consumer for real-time tweet delivery:
- 08:00 daily: economic calendar morning digest
- Every 60 min: check for new economic releases
- Continuous: X filtered stream pushes new tweets from configured accounts
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.alert_handler import TelegramAlertHandler
from bot.deepseek_client import DeepSeekClient
from bot.economic_calendar import morning_digest, check_releases
from bot.gemini_client import GeminiClient
from bot.relevance import Relevance
from bot.summarizer import Summarizer
from bot.telegram_sender import TelegramSender
from bot.translation import TranslationChain
from bot.translator import Translator
from bot.tweet_monitor import consume_stream, load_state, save_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def main() -> None:
    config = load_config()

    tg_cfg = config.get("telegram", {})
    sender = TelegramSender(
        token=tg_cfg["token"],
        channel_id=tg_cfg["channel_id"],
        alert_chat_id=tg_cfg.get("alert_chat_id", ""),
    )

    # Forward every warning/error logged anywhere (API requests, jobs, stream…)
    # to the alert chat. Scheduler job failures are logged by APScheduler itself.
    if tg_cfg.get("alert_chat_id"):
        logging.getLogger().addHandler(
            TelegramAlertHandler(
                send_alert=sender.send_alert,
                loop=asyncio.get_running_loop(),
                level=logging.getLevelName(str(tg_cfg.get("alert_level", "WARNING")).upper()),
                cooldown=float(tg_cfg.get("alert_cooldown_seconds", 60)),
            )
        )

    claude_cfg = config.get("claude") or {}
    claude_api_key = claude_cfg.get("api_key", "")
    gemini_cfg = config.get("gemini") or {}
    gemini_api_key = gemini_cfg.get("api_key", "")
    gemini = (
        GeminiClient(api_key=gemini_api_key, model=gemini_cfg.get("model", ""))
        if gemini_api_key
        else None
    )

    deepseek_cfg = config.get("deepseek") or {}
    deepseek_api_key = deepseek_cfg.get("api_key", "")

    # Translation: Gemini, then DeepSeek, then Claude — each retried, falling back to the next.
    providers = []
    if gemini:
        providers.append(("Gemini", gemini.translate))
    if deepseek_api_key:
        deepseek = DeepSeekClient(api_key=deepseek_api_key, model=deepseek_cfg.get("model", ""))
        providers.append(("DeepSeek", deepseek.translate))
    if claude_api_key:
        providers.append(("Claude", Translator(api_key=claude_api_key).translate))
    translate_fn = TranslationChain(providers).translate if providers else None
    promo_fn = gemini.is_promotional if gemini else None

    state = load_state()

    relevance = Relevance(api_key=claude_api_key) if claude_api_key else None
    validate_fn = relevance.is_relevant if relevance else None
    summarizer = Summarizer(api_key=claude_api_key) if claude_api_key else None
    summarize_fn = summarizer.summarize if summarizer else (gemini.summarize if gemini else None)
    classify_fn = summarizer.classify if summarizer else None

    scheduler = AsyncIOScheduler()

    cal_cfg = config.get("economic_calendar", {})

    # Morning digest at 08:00 UTC, Monday–Friday only
    scheduler.add_job(
        morning_digest,
        "cron",
        day_of_week="mon-fri",
        hour=8,
        minute=0,
        kwargs={"config": config, "send_fn": sender.send, "state": state},
        id="morning_digest",
    )

    # Hourly release check
    check_interval = cal_cfg.get("check_interval_minutes", 60)
    scheduler.add_job(
        check_releases,
        "interval",
        minutes=check_interval,
        kwargs={"config": config, "send_fn": sender.send, "state": state},
        id="check_releases",
    )

    # Tweet monitor — real-time X filtered stream, run as a background task
    # rather than a scheduler job (it's a long-lived connection, not a periodic call).
    stream_task = asyncio.create_task(
        consume_stream(
            config=config,
            translate_fn=translate_fn,
            send_fn=sender.send,
            state=state,
            validate_fn=validate_fn,
            summarize_fn=summarize_fn,
            classify_fn=classify_fn,
            promo_fn=promo_fn,
        ),
        name="x_stream_consumer",
    )

    def _on_stream_task_done(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        msg = (
            f"⚠️ X stream task stopped: {type(exc).__name__}: {exc}"
            if exc is not None
            else "⚠️ X stream task exited unexpectedly (no tweets will be received)."
        )
        asyncio.ensure_future(sender.send_alert(msg))

    stream_task.add_done_callback(_on_stream_task_done)

    scheduler.start()
    logger.info("Scheduler started. Jobs: %s", [j.id for j in scheduler.get_jobs()])
    await sender.send_alert("✅ Bot started.")

    # Send digest immediately on startup if it's a weekday past 08:00 UTC and not yet sent today
    now = datetime.now(timezone.utc)
    today = now.date()
    if (
        now.weekday() < 5
        and now.hour >= 8
        and state.get("last_digest_date") != str(today)
    ):
        logger.info("Past 08:00 UTC on a weekday and digest not yet sent — sending now.")
        asyncio.ensure_future(morning_digest(config=config, send_fn=sender.send, state=state))

    try:
        # Run indefinitely
        while True:
            await asyncio.sleep(60)
            save_state(state)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        stream_task.remove_done_callback(_on_stream_task_done)
        stream_task.cancel()
        try:
            await stream_task
        except (asyncio.CancelledError, Exception):
            pass
        await sender.send_alert("🛑 Bot stopped.")
        scheduler.shutdown()
        save_state(state)


if __name__ == "__main__":
    asyncio.run(main())
