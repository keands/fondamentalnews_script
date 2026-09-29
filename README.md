# fondamentalnewsbot

A Telegram bot that monitors financial news and posts market-moving information to a Telegram channel. It tracks economic calendar events and Twitter accounts, translates content to French (DeepSeek, Gemini or Claude), and uses AI to filter for relevance and drop promotional tweets.

## Features

- **Morning Digest** — posts today's economic calendar events (ForexFactory) at 08:00 UTC, Mon–Fri
- **Release Alerts** — detects when economic data is released (actual value becomes available) and sends an immediate alert
- **Twitter Monitor** — streams configured X accounts in real-time via the official X API filtered stream, summarizes new tweets and translates the summary to French (DeepSeek, Gemini or Claude)
- **AI Relevance Filter** — uses Claude (Haiku) to skip tweets that carry no market-moving signal
- **Promotion Filter** — never publishes promotional tweets (ads, promo codes, giveaways, newsletters/courses/webinars, "subscribe"/"sign up" calls…), using a keyword filter plus Gemini/Claude
- **Tweet lifecycle** — fetch the full tweet from X (long posts included, retweets skipped) → filter (promotion + relevance) → summarize → translate the summary to French → send **one** Telegram message per tweet
- **Error Alerts** — forwards every logged warning/error (failed API requests, job errors, stream disconnects…) to a private Telegram chat

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| Telegram Bot Token | [BotFather](https://t.me/BotFather) |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| Gemini API key (optional) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| DeepSeek API key (optional) | [platform.deepseek.com](https://platform.deepseek.com) |
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
  alert_level: "WARNING"        # optional: minimum log level forwarded (WARNING or ERROR)
  alert_cooldown_seconds: 60    # optional: identical alerts are grouped within this window

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

gemini:
  api_key: "YOUR_GEMINI_KEY"     # optional — used for translation when set
  model: "gemini-flash-latest"   # optional

deepseek:
  api_key: "YOUR_DEEPSEEK_KEY"   # optional — handles every AI task when set
  model: "deepseek-v4-flash"     # optional
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
    ├── gemini_client.py     # Gemini translation, summary & promotion check
    ├── deepseek_client.py   # DeepSeek: summary, translation, relevance, promo, hashtags
    ├── translation.py       # Translation retries & provider fallback
    ├── promo_filter.py      # Keyword-based promotional tweet filter
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
Optional. If omitted, all tweets pass through without AI filtering and no summaries are generated
(unless a Gemini key is set, in which case Gemini generates the summaries).

### `gemini.api_key` / `gemini.model`
Optional. When set, Gemini is a translation fallback (after DeepSeek), and Gemini
also checks each tweet for promotional content. `model` defaults to `gemini-flash-latest`.

### `deepseek.api_key` / `deepseek.model`
Optional. When set, DeepSeek handles **every** AI task: summary, translation, relevance filter,
promotion check and hashtags (each call retried twice on errors). Gemini and Claude are then only used
as translation fallbacks. Without DeepSeek, the bot uses Claude/Gemini as before. `model` defaults to `deepseek-v4-flash`.

### Translation fallback
Translation tries each configured provider in order — **DeepSeek → Gemini → Claude**. Each provider is
retried twice (after 2 s and 5 s) on errors such as quota exhaustion (HTTP 429) or an empty answer
before moving to the next one. If every provider fails, the message is sent untranslated and an error
is sent to `alert_chat_id`.

Promotional tweets are always dropped by a keyword filter, even without any API key.

---

## Stopping

```bash
# systemd
sudo systemctl stop fondamentalnewsbot

# Local
Ctrl+C
```

The bot sends a startup (`✅ Bot started.`) and shutdown (`🛑 Bot stopped.`) notification to `alert_chat_id`.

Every log record at `alert_level` or above (API request failures, scheduler job exceptions, X stream errors, etc.) is also forwarded there. Identical messages are sent at most once per `alert_cooldown_seconds`; repeats are counted in the next alert.
