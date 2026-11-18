# fondamentalnewsbot

A Telegram bot that monitors financial news and posts market-moving information to a Telegram channel. It tracks economic calendar events and Twitter accounts, translates content to French (DeepSeek V4 Flash via OpenRouter, Gemini or Claude), and uses AI to filter for relevance and drop promotional tweets.

## Features

- **Morning Digest** — posts today's economic calendar events (ForexFactory) at 08:00 UTC, Mon–Fri
- **Release Alerts** — detects when economic data is released (actual value becomes available) and sends an immediate alert
- **Twitter Monitor** — streams configured X accounts in real-time via the official X API filtered stream, summarizes new tweets and translates the summary to French (DeepSeek V4 Flash via OpenRouter, Gemini or Claude)
- **AI Relevance Filter** — skips tweets that carry no market-moving signal
- **Promotion Filter** — never publishes promotional tweets (ads, promo codes, giveaways, newsletters/courses/webinars, "subscribe"/"sign up" calls…), using a keyword filter plus an AI check
- **Tweet lifecycle** — fetch the full tweet from X (long posts included, retweets skipped) → filter (promotion + relevance) → summarize → translate the summary to French → send **one** Telegram message per tweet
- **Error Alerts** — forwards every logged warning/error (failed API requests, job errors, stream disconnects…) to a private Telegram chat

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| Telegram Bot Token | [BotFather](https://t.me/BotFather) |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| Gemini API key (optional) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| OpenRouter API key (optional) | [openrouter.ai/keys](https://openrouter.ai/keys) |
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
  restart_button: true          # optional: restart button in the alert chat (default true)
  admin_ids: [123456789]        # optional: only these Telegram user IDs may use the button

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

openrouter:
  api_key: "YOUR_OPENROUTER_KEY"        # optional — handles every AI task when set
  model: "deepseek/deepseek-v4-flash"   # optional
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
├── requirements-dev.txt     # + pytest (used by the deployment)
├── deploy/                  # Automatic deployment (script, systemd timer, installer)
└── bot/
    ├── economic_calendar.py # ForexFactory fetching & formatting
    ├── tweet_monitor.py     # X filtered-stream consumer & formatting
    ├── ai.py                # AI capabilities (translate, summarize, relevance, promo, French check, hashtags)
    ├── fallback.py          # FallbackChain: retries + provider fallback + failure policy
    ├── prompts.py           # Every prompt sent to the AI providers
    ├── openrouter_client.py # OpenRouter provider (DeepSeek V4 Flash by default)
    ├── gemini_client.py     # Gemini provider
    ├── claude_client.py     # Claude provider
    ├── promo_filter.py      # Keyword-based promotional tweet filter
    ├── alert_handler.py     # Forwards logged warnings/errors to the alert chat
    ├── telegram_control.py  # Telegram restart button (polling, authorization, confirmation)
    ├── restart.py           # In-place process restart
    └── telegram_sender.py   # Telegram message delivery
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

### AI providers: `openrouter`, `gemini`, `claude`
Each section takes an `api_key` (and an optional `model`; defaults: `deepseek/deepseek-v4-flash` for
OpenRouter, `gemini-flash-latest` for Gemini). All are optional: every configured provider is used,
in this order — **OpenRouter → Gemini → Claude** — for **every** AI task (translation, summary,
relevance filter, promotion check, French check, hashtags).

For each task, a provider is retried on errors (quota exhaustion, outage, empty answer) after 2 s
(and 5 s for translation and summaries) before the next provider is tried. If every provider fails:

| Task | Result |
|------|--------|
| translation | error sent to `alert_chat_id`, the tweet is **not** sent |
| summary | tweet **not** sent |
| French check | text rejected (never sent in doubt) |
| relevance filter | tweet passes |
| promotion check | tweet passes (the keyword filter still applies) |
| hashtags | message sent without hashtags |

Without any AI key, tweets pass through unfiltered, unsummarized and untranslated.

Promotional tweets are always dropped by a keyword filter, even without any API key.

---

## Restarting from Telegram

When `alert_chat_id` is set, the startup message (`✅ Bot started.`) carries a **🔄 Redémarrer le bot**
button, and `/menu` in the same chat shows it again. Pressing it asks for a confirmation (✅ / ❌);
on confirmation the bot stops its stream and scheduler, saves its state and restarts itself. It
comes back with a new `✅ Bot started.` message, running the latest code on disk and the current
`config.yaml` (after a `git pull`, for example).

- **Who can use it**: only the `alert_chat_id` chat. If that chat is a group, set `telegram.admin_ids`
  so that only these users can. Presses from anywhere else are ignored (and logged as a warning).
- **How**: the process replaces itself with a fresh interpreter running the same command line, so it
  works under systemd, Docker or a plain shell without depending on a restart policy.
- **Requirement**: the bot now listens to Telegram (long polling), and Telegram allows a single
  listener per bot token. Do not run a second copy of the bot with the same token (a development
  copy, for instance), or both will fail with "Conflict" errors.
- **Disable it** with `telegram.restart_button: false`.
- Presses made while the bot is down are ignored, so an old button can never restart it by surprise.

---

## Automatic deployment

Optional. Every night at 03:30 UTC (a quiet hour; changeable, see below) the server checks GitHub for a
new commit on `master` and deploys it **only if it is safe**:

1. nothing new → nothing happens;
2. a new commit is installed (`pip install -r requirements-dev.txt`) and tested (`pytest`) in a
   throwaway checkout — if that fails, the running bot and its files are **left untouched**;
3. otherwise the checkout is fast-forwarded and the service restarted; if the bot does not stay up
   (crash loop), the previous commit is restored and restarted.

Every outcome is sent to the alert chat (`🚀 Déployé`, `⚠️ Déploiement annulé`, `↩️ Retour à la version`).
`config.yaml` and `state.json` are never touched. A deployment also stops if the checkout has local
modifications, is not on `master` or has diverged from GitHub.

**Prerequisite — the server must be able to `git fetch` without a human.** The repository is private,
so use a read-only *deploy key* (skip this if `sudo -u YOUR_USER git fetch origin` already works):

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/fondamentalnews_deploy
cat ~/.ssh/fondamentalnews_deploy.pub    # GitHub: repository > Settings > Deploy keys > Add (read-only)
printf 'Host github.com\n  IdentityFile ~/.ssh/fondamentalnews_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
git remote set-url origin git@github.com:OWNER/REPO.git
git fetch origin master                   # must work without any prompt
```

**Install (once, on the server):**

```bash
pip install -r requirements-dev.txt      # in the bot's venv, for pytest
sudo ./deploy/install.sh                 # SERVICE=name if your unit is not "fondamentalnewsbot"
```

It installs a systemd service + timer and one narrow sudo rule that lets the bot's user run
`systemctl restart <service>` — nothing else.

```bash
sudo systemctl start fondamentalnewsbot-deploy.service    # deploy right now
systemctl list-timers fondamentalnewsbot-deploy.timer     # next run
journalctl -u fondamentalnewsbot-deploy -n 50             # what happened
sudo systemctl edit fondamentalnewsbot-deploy.timer       # change the hour, e.g.:
#   [Timer]
#   OnCalendar=
#   OnCalendar=*-*-* 05:00:00 UTC
```

A deployment restarts the bot through systemd, so expect `🛑 Bot stopped.` then `✅ Bot started.`.
`systemctl stop`/`restart` and Ctrl+C stop the bot cleanly (the state is saved first; it holds the
morning digest date and the release alerts already sent, which avoids duplicates after a restart).
Docker deployments are not covered.

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
