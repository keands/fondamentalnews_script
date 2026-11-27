#!/usr/bin/env bash
# Safe automatic deployment of fondamentalnewsbot: fetch, verify the new commit, then restart.
#
# - Nothing to deploy      -> exit 0, nothing touched.
# - New commit             -> installed and tested in a throwaway checkout FIRST. If that fails,
#                             the running bot and its working tree are left untouched.
# - Tests pass             -> fast-forward the working tree, restart the service, check it stays up.
#                             If it does not, roll back to the previous commit and restart again.
# Every outcome is sent to the Telegram alert chat. config.yaml and state.json are never touched.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

SERVICE="${SERVICE:-fondamentalnewsbot}"
BRANCH="${BRANCH:-master}"
SYSTEMCTL="${SYSTEMCTL:-systemctl}"
HEALTH_WAIT="${HEALTH_WAIT:-25}"   # seconds the restarted service must stay up
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if [ -x "$APP_DIR/.venv/bin/python" ]; then PYTHON="$APP_DIR/.venv/bin/python"; else PYTHON="$(command -v python3)"; fi
fi
TEST_CMD="${TEST_CMD:-$PYTHON -m pytest -q}"
RESTART_CMD="${RESTART_CMD:-sudo -n $SYSTEMCTL restart $SERVICE}"
NOTIFY_CMD="${NOTIFY_CMD:-$PYTHON $APP_DIR/deploy/notify.py}"

log() { echo "$(date -u +%FT%TZ) $*"; }
notify() { $NOTIFY_CMD "$1" || log "(notification not sent)"; }
fail() { log "FAILED: $1"; notify "⚠️ Déploiement annulé : $1"; exit 1; }

install_deps() {  # run from a checkout directory
  if [ -n "${INSTALL_CMD:-}" ]; then $INSTALL_CMD; return; fi
  local req=requirements-dev.txt
  [ -f "$req" ] || req=requirements.txt
  "$PYTHON" -m pip install -q -r "$req"
}

healthy() {
  [ "$($SYSTEMCTL is-active "$SERVICE" 2>/dev/null || true)" = "active" ] || return 1
  # NRestarts counts automatic restarts since our manual restart: non-zero means a crash loop.
  [ "$($SYSTEMCTL show -p NRestarts --value "$SERVICE" 2>/dev/null || echo 0)" = "0" ]
}

exec 9>"$APP_DIR/.deploy.lock"
flock -n 9 || { log "Another deployment is running"; exit 0; }

[ "$(git rev-parse --abbrev-ref HEAD)" = "$BRANCH" ] || fail "le dépôt du serveur n'est pas sur la branche $BRANCH"
{ git diff --quiet && git diff --cached --quiet; } || fail "modifications locales non commitées sur le serveur"
git fetch -q origin "$BRANCH" || fail "git fetch impossible (accès à GitHub ?)"

OLD="$(git rev-parse HEAD)"
NEW="$(git rev-parse FETCH_HEAD)"
if [ "$OLD" = "$NEW" ] || git merge-base --is-ancestor "$NEW" "$OLD"; then
  log "Nothing to deploy ($(git rev-parse --short HEAD))"; exit 0
fi
git merge-base --is-ancestor "$OLD" "$NEW" || fail "l'historique du serveur a divergé de origin/$BRANCH"
SHORT_OLD="$(git rev-parse --short "$OLD")"; SHORT_NEW="$(git rev-parse --short "$NEW")"
COUNT="$(git rev-list --count "$OLD..$NEW")"
SUBJECT="$(git log -1 --format=%s "$NEW")"
log "Deploying $SHORT_OLD -> $SHORT_NEW ($COUNT commit(s))"

# 1. Verify the new commit away from the live checkout.
WORK="$(mktemp -d)"
trap 'git -C "$APP_DIR" worktree remove --force "$WORK/src" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT
git worktree add -q --detach "$WORK/src" "$NEW"
(cd "$WORK/src" && install_deps) || fail "installation des dépendances impossible pour $SHORT_NEW — rien n'a été changé"
if ! (cd "$WORK/src" && $TEST_CMD) >"$WORK/tests.log" 2>&1; then
  tail -n 20 "$WORK/tests.log"
  fail "tests en échec sur $SHORT_NEW — rien n'a été changé"
fi

# 2. Go live.
rollback() {
  log "Rolling back to $SHORT_OLD"
  git reset -q --hard "$OLD"
  install_deps >/dev/null 2>&1 || true
  $RESTART_CMD || true
  notify "↩️ Retour à la version $SHORT_OLD ($1)"
}
git merge -q --ff-only "$NEW" || fail "fast-forward impossible vers $SHORT_NEW"
if ! $RESTART_CMD; then rollback "redémarrage refusé"; exit 1; fi
sleep "$HEALTH_WAIT"
if ! healthy; then rollback "le service ne tient pas après $SHORT_NEW"; exit 1; fi

log "Deployed $SHORT_NEW"
notify "🚀 Déployé : $SHORT_NEW — $SUBJECT ($COUNT commit(s))"
