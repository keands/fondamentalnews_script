#!/usr/bin/env bash
# One-time setup of the nightly deployment on the server:  sudo ./deploy/install.sh
#   - installs a systemd service + timer that run deploy/deploy.sh
#   - lets the bot's user restart the bot's service (and nothing else) through sudo
# Optional environment: APP_USER (default: owner of the checkout), SERVICE (default: fondamentalnewsbot).
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="${APP_USER:-$(stat -c %U "$APP_DIR")}"
SERVICE="${SERVICE:-fondamentalnewsbot}"
UNIT_DIR="${UNIT_DIR:-/etc/systemd/system}"
SUDOERS_DIR="${SUDOERS_DIR:-/etc/sudoers.d}"
NO_SYSTEMD="${NO_SYSTEMD:-}"   # set by the tests: skip root check, visudo and systemctl

if [ -z "$NO_SYSTEMD" ] && [ "$(id -u)" != 0 ]; then
  echo "Run as root: sudo $0" >&2; exit 1
fi
SYSTEMCTL="$(command -v systemctl || echo /usr/bin/systemctl)"

chmod +x "$APP_DIR/deploy/deploy.sh"
for kind in service timer; do
  sed "s|@APP_DIR@|$APP_DIR|g; s|@APP_USER@|$APP_USER|g; s|@SERVICE@|$SERVICE|g" \
    "$APP_DIR/deploy/fondamentalnewsbot-deploy.$kind.in" > "$UNIT_DIR/fondamentalnewsbot-deploy.$kind"
done

RULE="$APP_USER ALL=(root) NOPASSWD: $SYSTEMCTL restart $SERVICE"
if [ -z "$NO_SYSTEMD" ]; then
  tmp="$(mktemp)"; echo "$RULE" > "$tmp"
  visudo -cf "$tmp" >/dev/null
  install -m 0440 "$tmp" "$SUDOERS_DIR/fondamentalnewsbot-deploy"; rm -f "$tmp"
  "$SYSTEMCTL" daemon-reload
  "$SYSTEMCTL" enable --now fondamentalnewsbot-deploy.timer
  "$SYSTEMCTL" list-timers fondamentalnewsbot-deploy.timer --no-pager
else
  echo "$RULE" > "$SUDOERS_DIR/fondamentalnewsbot-deploy"
fi
echo "Installed. Deploy now with: sudo systemctl start fondamentalnewsbot-deploy.service"
