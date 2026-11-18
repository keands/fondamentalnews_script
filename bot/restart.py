"""Restart the bot process in place."""

import logging
import os
import sys

logger = logging.getLogger(__name__)


def restart_process() -> None:
    """Replace this process by a fresh interpreter running the same command line. Never returns.

    The new process re-imports the code and re-reads config.yaml. It keeps the PID, so it works
    the same under systemd, Docker or a plain shell, without relying on a restart policy. If the
    exec fails, exit with an error status so that a supervisor (systemd, Docker) restarts the bot.
    """
    for stream in (sys.stdout, sys.stderr):
        stream.flush()
    for handler in logging.getLogger().handlers:
        handler.flush()
    try:
        # orig_argv keeps the interpreter flags (e.g. "python -u main.py").
        os.execv(sys.executable, [sys.executable, *sys.orig_argv[1:]])
    except OSError:
        logger.exception("Could not restart the process in place — exiting so a supervisor can")
        raise SystemExit(1)
