"""Send one message to the Telegram alert chat. Used by deploy.sh (standard library + PyYAML only,
so it still works when the bot's own code or dependencies are broken).

    python deploy/notify.py "message"
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

import yaml

API_URL = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org")
CONFIG = Path(os.environ.get("CONFIG", Path(__file__).resolve().parents[1] / "config.yaml"))


def send(text: str) -> bool:
    """Return True if a message was sent, False if there is no alert chat configured."""
    telegram = yaml.safe_load(CONFIG.read_text(encoding="utf-8")).get("telegram", {})
    chat_id = telegram.get("alert_chat_id")
    if not chat_id:
        return False
    request = urllib.request.Request(
        f"{API_URL}/bot{telegram['token']}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(request, timeout=20).close()
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: notify.py MESSAGE")
    send(sys.argv[1])
