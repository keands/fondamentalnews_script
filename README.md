# fondamentalnewsbot

A Telegram bot that monitors financial news and posts market-moving information to a Telegram channel. It tracks economic calendar events and Twitter accounts, translates content to French, and uses Claude AI to filter for relevance.

## Features

- **Morning Digest** — posts today's economic calendar events (ForexFactory) at 08:00 UTC, Mon–Fri
- **Release Alerts** — detects when economic data is released (actual value becomes available) and sends an immediate alert
- **Twitter Monitor** — polls configured Twitter accounts for new tweets, translates them to French via DeepL, and optionally summarizes them
- **AI Relevance Filter** — uses Claude (Haiku) to skip tweets that carry no market-moving signal
- **Error Alerts** — sends scheduler errors to a private Telegram chat

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| Telegram Bot Token | [BotFather](https://t.me/BotFather) |
| DeepL API key | [deepl.com](https://www.deepl.com/pro-api) |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| Twitter account(s) | for scraping via twscrape |

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

deepl:
  api_key: "YOUR_DEEPL_KEY"

twitter:
  max_messages_per_cycle: 3
  poll_interval_minutes: 10
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

### 2. Add Twitter credentials

Create `accounts.txt` with one Twitter account per line in twscrape format:

```
username:password:email:email_password:auth_token=...; ct0=...
```

Load the file to create database user for the api

```bash
twscrape add_accounts ./accounts.txt username:password:email:email_password:cookies
``` 

If success run the command asked

> **Security**: `accounts.txt` contains sensitive credentials. Never commit it to git. Add it to `.gitignore`.

### 3. Create empty state files (first run)

```bash
echo '{}' > state.json
touch accounts.db
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
| `tweet_monitor` | Every 10 min (configurable) | Checks Twitter accounts for new tweets |

On startup, if it is past 08:00 UTC on a weekday and the digest has not been sent today, it fires immediately.

---

## Project Structure

```
fondamentalnewsbot/
├── main.py                  # Entry point, scheduler setup
├── config.yaml              # All configuration (API keys, accounts, filters)
├── accounts.txt             # Twitter credentials for twscrape (keep secret)
├── accounts.db              # twscrape session database (auto-managed)
├── state.json               # Runtime state (last tweet IDs, posted events)
├── requirements.txt
└── bot/
    ├── economic_calendar.py # ForexFactory fetching & formatting
    ├── tweet_monitor.py     # Twitter polling & formatting
    ├── telegram_sender.py   # Telegram message delivery
    ├── translator.py        # DeepL translation
    ├── relevance.py         # Claude AI relevance filter
    └── summarizer.py        # Claude AI tweet summarizer
```

---

## Configuration Reference

### `twitter.accounts`
Each entry needs:
- `handle` — Twitter username without `@`
- `label` — Display name shown in Telegram messages

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
