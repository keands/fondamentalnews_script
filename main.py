"""fondamentalnewsbot — Entry point.

Starts the APScheduler and runs scheduled jobs:
- 08:00 daily: economic calendar morning digest
- Every 60 min: check for new economic releases
- Every 30 min: check configured Twitter accounts for new tweets
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

import yaml
from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.economic_calendar import morning_digest, check_releases
from bot.relevance import Relevance
from bot.summarizer import Summarizer
from bot.telegram_sender import TelegramSender
from bot.translator import Translator
from bot.tweet_monitor import check_new_tweets, load_state, save_state

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

    claude_cfg = config.get("claude", {})
    claude_api_key = claude_cfg.get("api_key", "")
    translator = Translator(api_key=claude_api_key) if claude_api_key else None
    translate_fn = translator.translate if translator else None

    state = load_state()

    relevance = Relevance(api_key=claude_api_key) if claude_api_key else None
    validate_fn = relevance.is_relevant if relevance else None
    summarizer = Summarizer(api_key=claude_api_key) if claude_api_key else None
    summarize_fn = summarizer.summarize if summarizer else None

    scheduler = AsyncIOScheduler()

    def _on_job_error(event):
        job_id = event.job_id
        exc = event.exception
        msg = f"⚠️ Bot error in job `{job_id}`:\n{type(exc).__name__}: {exc}"
        asyncio.ensure_future(sender.send_alert(msg))

    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    cal_cfg = config.get("economic_calendar", {})
    twitter_cfg = config.get("twitter", {})

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

    # Tweet monitor
    poll_interval = twitter_cfg.get("poll_interval_minutes", 30)
    scheduler.add_job(
        check_new_tweets,
        "interval",
        minutes=poll_interval,
        kwargs={
            "config": config,
            "translate_fn": translate_fn,
            "send_fn": sender.send,
            "state": state,
            "validate_fn": validate_fn,
            "summarize_fn": summarize_fn,
        },
        id="tweet_monitor",
    )

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
        await sender.send_alert("🛑 Bot stopped.")
        scheduler.shutdown()
        save_state(state)


if __name__ == "__main__":
    asyncio.run(main())
