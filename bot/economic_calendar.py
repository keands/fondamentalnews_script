"""Fetch and filter ForexFactory economic calendar events."""

import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

logger = logging.getLogger(__name__)

FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

PARIS_TZ = ZoneInfo("Europe/Paris")

IMPACT_RANK = {"Non-Economic": 0, "Low": 1, "Medium": 2, "High": 3}

COUNTRY_FLAG = {
    "USD": "🇺🇸",
    "EUR": "🇪🇺",
    "GBP": "🇬🇧",
    "JPY": "🇯🇵",
}


def _min_impact_rank(min_impact: str) -> int:
    return IMPACT_RANK.get(min_impact.capitalize(), 2)


async def fetch_events(countries: list[str], min_impact: str) -> list[dict[str, Any]]:
    """Return all events for today matching country and impact filters."""
    min_rank = _min_impact_rank(min_impact)
    today = datetime.now(timezone.utc).date()

    async with aiohttp.ClientSession() as session:
        async with session.get(FF_CALENDAR_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

    results = []
    for event in data:
        country = event.get("country", "").upper()
        if country not in countries:
            continue
        impact = event.get("impact", "")
        if IMPACT_RANK.get(impact, 0) < min_rank:
            continue
        # Parse event date
        date_str = event.get("date", "")
        try:
            event_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if event_dt.date() != today:
            continue
        results.append(event)

    results.sort(key=lambda e: e.get("date", ""))
    return results


def format_morning_digest(events: list[dict[str, Any]]) -> str:
    """Format a morning digest message listing today's events."""
    if not events:
        return "📅 No significant economic events scheduled for today."

    today_label = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    lines = [f"📅 *Economic Calendar — {today_label}*\n"]
    for ev in events:
        flag = COUNTRY_FLAG.get(ev.get("country", "").upper(), "🌐")
        time_str = ""
        date_str = ev.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            dt_paris = dt.astimezone(PARIS_TZ)
            time_str = f"{dt.strftime('%H:%M')} UTC | {dt_paris.strftime('%H:%M')} Paris"
        except (ValueError, AttributeError):
            pass
        name = ev.get("title", "Unknown Event")
        impact = ev.get("impact", "")
        impact_icon = "🔴" if impact == "High" else "🟡"
        forecast = ev.get("forecast", "").strip()
        previous = ev.get("previous", "").strip()
        line = f"{flag} {time_str} {impact_icon} *{name}*"
        if forecast or previous:
            fp_parts = []
            if forecast:
                fp_parts.append(f"F: {forecast}")
            if previous:
                fp_parts.append(f"P: {previous}")
            line += "\n    " + "  |  ".join(fp_parts)
        lines.append(line)

    return "\n".join(lines)


def format_release_alert(event: dict[str, Any]) -> str:
    """Format a release alert when actual data is available."""
    flag = COUNTRY_FLAG.get(event.get("country", "").upper(), "🌐")
    name = event.get("title", "Unknown Event")
    actual = event.get("actual", "N/A")
    forecast = event.get("forecast", "") or "—"
    previous = event.get("previous", "") or "—"
    impact = event.get("impact", "")
    impact_icon = "🔴" if impact == "High" else "🟡"

    return (
        f"{flag} {impact_icon} *{name}*\n"
        f"Actual: *{actual}*  |  Forecast: {forecast}  |  Previous: {previous}"
    )


async def morning_digest(config: dict, send_fn, state: dict | None = None) -> None:
    """Fetch events and send morning digest."""
    cal_cfg = config.get("economic_calendar", {})
    countries = [c.upper() for c in cal_cfg.get("countries", ["USD", "EUR", "GBP", "JPY"])]
    min_impact = cal_cfg.get("min_impact", "medium")

    try:
        events = await fetch_events(countries, min_impact)
        message = format_morning_digest(events)
        await send_fn(message)
        if state is not None:
            state["last_digest_date"] = str(datetime.now(timezone.utc).date())
    except Exception:
        logger.exception("Failed to send morning digest")


async def check_releases(config: dict, send_fn, state: dict) -> None:
    """Check for newly released economic data and post alerts."""
    cal_cfg = config.get("economic_calendar", {})
    countries = [c.upper() for c in cal_cfg.get("countries", ["USD", "EUR", "GBP", "JPY"])]
    min_impact = cal_cfg.get("min_impact", "medium")

    try:
        events = await fetch_events(countries, min_impact)
    except Exception:
        logger.exception("Failed to fetch economic calendar")
        return

    posted = state.setdefault("posted_releases", [])
    for event in events:
        actual = event.get("actual", "")
        if not actual:
            continue
        event_id = f"{event.get('date', '')}_{event.get('title', '')}"
        if event_id in posted:
            continue
        message = format_release_alert(event)
        try:
            await send_fn(message)
            posted.append(event_id)
        except Exception:
            logger.exception("Failed to send release alert for %s", event_id)
