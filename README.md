# fondamentalnewsbot

A Telegram bot that monitors financial news and posts market-moving information to a Telegram channel. It tracks economic calendar events and Twitter accounts, translates content to French, and uses Claude AI to filter for relevance.

## Features

- **Morning Digest** — posts today's economic calendar events (ForexFactory) at 08:00 UTC, Mon–Fri
- **Release Alerts** — detects when economic data is released (actual value becomes available) and sends an immediate alert
- **Twitter Monitor** — streams configured X accounts in real-time via the official X API filtered stream, translates new tweets to French via Claude, and optionally summarizes them
- **AI Relevance Filter** — uses Claude (Haiku) to skip tweets that carry no market-moving signal
- **Error Alerts** — sends scheduler errors to a private Telegram chat

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| Telegram Bot Token | [BotFather](https://t.me/BotFather) |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| X API Bearer Token | [developer.x.com](https://developer.x.com) — needs access to the filtered stream endpoint (pay-per-use plan or higher) |

## Setup

### 1. Clone and configure

```bash
git clone <repo-url>
cd fondamentalnewsbot
cp config.yaml config.yaml   # already present — just edit it
```

Edit `config.yaml`:

```yaml
telegram:
  token: "YOUR_BOT_TOKEN"
  channel_id: "@your_channel"   # or numeric ID
  alert_chat_id: "YOUR_CHAT_ID" # your personal chat for error DMs

twitter:
  bearer_token: "YOUR_X_API_BEARER_TOKEN"
  max_messages_per_window: 3
  window_minutes: 5
  accounts:
    - handle: "federalreserve"
      label: "Federal Reserve"
    # add more accounts here

economic_calendar:
  countries: [USD, EUR, GBP, JPY]
  min_impact: medium   # medium | high
  check_interval_minutes: 60

claude:
  api_key: "YOUR_ANTHROPIC_KEY"  # optional — disables AI filter if omitted
```

### 2. Add an X API Bearer Token

Create a project + App at [developer.x.com](https://developer.x.com) with access to the filtered
stream endpoint (`GET /2/tweets/search/stream`), generate an **App-only Bearer Token**, and set it
as `twitter.bearer_token` in `config.yaml`.

No account credentials or login cookies are needed — the bot uses the official read-only API.

> **Security**: `config.yaml` contains sensitive credentials. Never commit it to git. Add it to `.gitignore`.

### 3. Create empty state file (first run)

```bash
echo '{}' > state.json
```

---

## Running

### Option A — systemd (production)

```bash
# 1. Create the service file
sudo nano /etc/systemd/system/fondamentalnewsbot.service
```

Paste this content (adjust `User` and paths):

```ini
[Unit]
Description=fondamentalnewsbot
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/fondamentalnewsbot
ExecStart=/path/to/fondamentalnewsbot/.venv/bin/python -u main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# 2. Enable and start
sudo systemctl daemon-reload
sudo systemctl enable fondamentalnewsbot
sudo systemctl start fondamentalnewsbot

# 3. Check status / follow logs
sudo systemctl status fondamentalnewsbot
sudo journalctl -u fondamentalnewsbot -f
```

### Option B — Local (development)

```bash
source .venv/Scripts/activate   # Windows Git Bash
# or: source .venv/bin/activate  # Linux/macOS

pip install -r requirements.txt
python main.py
```

---

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| `morning_digest` | 08:00 UTC, Mon–Fri | Posts today's economic events |
| `check_releases` | Every 60 min (configurable) | Posts alerts when actual data is available |
| `tweet_monitor` | Continuous (real-time stream) | Streams new tweets from configured X accounts |

On startup, if it is past 08:00 UTC on a weekday and the digest has not been sent today, it fires immediately.

---

## Project Structure

```
fondamentalnewsbot/
├── main.py                  # Entry point, scheduler + stream task setup
├── config.yaml              # All configuration (API keys, accounts, filters)
├── state.json               # Runtime state (last tweet IDs, posted events)
├── requirements.txt
└── bot/
    ├── economic_calendar.py # ForexFactory fetching & formatting
    ├── tweet_monitor.py     # X filtered-stream consumer & formatting
    ├── telegram_sender.py   # Telegram message delivery
    ├── translator.py        # Claude translation
    ├── relevance.py         # Claude AI relevance filter
    └── summarizer.py        # Claude AI tweet summarizer
```

---

## Configuration Reference

### `twitter.bearer_token`
X API App-only Bearer Token, used to authenticate the filtered stream connection.

### `twitter.accounts`
Each entry needs:
- `handle` — X username without `@` (used to build a `from:` stream rule)
- `label` — Display name shown in Telegram messages

Adding/removing a handle here takes effect on the next restart (stream rules are re-synced at startup).

### `twitter.max_messages_per_window` / `twitter.window_minutes`
Caps how many tweets get posted to Telegram within a rolling time window, to guard against a burst
of activity flooding the channel.

### `economic_calendar.min_impact`
- `medium` — includes Medium and High impact events
- `high` — High impact only

### `claude.api_key`
Optional. If omitted, all tweets pass through without AI filtering and no summaries are generated.

---

## Stopping

```bash
# systemd
sudo systemctl stop fondamentalnewsbot

# Local
Ctrl+C
```

The bot sends a startup (`✅ Bot started.`) and shutdown (`🛑 Bot stopped.`) notification to `alert_chat_id`.
