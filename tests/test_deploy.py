"""Tests for deploy/deploy.sh, install.sh and notify.py using real git repositories and stubbed systemd."""

import fcntl
import http.server
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}


def git(cwd, *args):
    env = {**os.environ, **GIT_ENV}
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True,
                          text=True).stdout.strip()


def write_exec(path, body):
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(0o755)


class Server:
    """A bare 'GitHub' remote, a 'server' checkout running deploy.sh, and a 'developer' checkout."""

    def __init__(self, tmp):
        self.tmp = tmp
        remote, self.dev, self.app = tmp / "remote.git", tmp / "dev", tmp / "server"
        git(tmp, "init", "-q", "--bare", "-b", "master", str(remote))
        git(tmp, "clone", "-q", str(remote), str(self.dev))
        shutil.copytree(REPO / "deploy", self.dev / "deploy")
        (self.dev / ".gitignore").write_text("config.yaml\nstate.json\n.deploy.lock\n")
        (self.dev / "VERSION").write_text("1\n")
        self.commit("v1")
        git(self.dev, "push", "-q", "origin", "master")
        git(tmp, "clone", "-q", str(remote), str(self.app))
        # Untracked runtime files that a deployment must never touch.
        (self.app / "config.yaml").write_text("secret: 1\n")
        (self.app / "state.json").write_text('{"last_digest_date": "2026-01-01"}')

        self.bin = tmp / "bin"
        self.bin.mkdir()
        self.log = tmp / "calls.log"
        self.service_state = tmp / "service_state"
        self.service_state.write_text("active")
        write_exec(self.bin / "systemctl", f'case "$1" in is-active) cat {self.service_state};; '
                                           f'show) echo 0;; esac\n')
        # A restart "starts" the version in the working tree: it crashes if the new code ships BROKEN.
        write_exec(self.bin / "restart", f'echo restart >> {self.log}\n'
                                         f'if [ -e {self.app}/BROKEN ]; then echo failed > {self.service_state};'
                                         f' else echo active > {self.service_state}; fi\n')
        write_exec(self.bin / "notify", f'echo "notify: $1" >> {self.log}\n')
        write_exec(self.bin / "tests", "test ! -e BREAK_TESTS\n")

    def commit(self, message, **files):
        for name, content in files.items():
            (self.dev / name).write_text(content)
        git(self.dev, "add", "-A")
        git(self.dev, "commit", "-q", "-m", message)

    def release(self, message, **files):
        self.commit(message, **files)
        git(self.dev, "push", "-q", "origin", "master")

    def deploy(self, **env):
        full = {**os.environ, **GIT_ENV, "SERVICE": "testsvc", "SYSTEMCTL": str(self.bin / "systemctl"),
                "HEALTH_WAIT": "0", "PYTHON": sys.executable, "INSTALL_CMD": "true",
                "TEST_CMD": str(self.bin / "tests"), "RESTART_CMD": str(self.bin / "restart"),
                "NOTIFY_CMD": str(self.bin / "notify"), **env}
        return subprocess.run([str(self.app / "deploy" / "deploy.sh")], cwd=self.app, env=full,
                              capture_output=True, text=True)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def head(self):
        return git(self.app, "rev-parse", "HEAD")


@pytest.fixture
def server(tmp_path):
    return Server(tmp_path)


def test_nothing_to_deploy_touches_nothing(server):
    result = server.deploy()
    assert result.returncode == 0, result.stderr
    assert server.calls() == []


def test_new_commit_is_tested_deployed_and_announced(server):
    server.release("add feature", VERSION="2\n")
    result = server.deploy()
    assert result.returncode == 0, result.stdout + result.stderr
    assert (server.app / "VERSION").read_text() == "2\n"
    assert server.head() == git(server.dev, "rev-parse", "HEAD")
    calls = server.calls()
    assert calls[0] == "restart" and len(calls) == 2
    assert calls[1].startswith("notify: 🚀 Déployé") and "add feature" in calls[1]


def test_runtime_files_are_never_touched(server):
    server.release("v2", VERSION="2\n")
    server.deploy()
    assert (server.app / "config.yaml").read_text() == "secret: 1\n"
    assert json.loads((server.app / "state.json").read_text())["last_digest_date"] == "2026-01-01"


def test_failing_tests_change_nothing_and_alert(server):
    before = server.head()
    server.release("breaks the tests", BREAK_TESTS="x")
    result = server.deploy()
    assert result.returncode == 1
    assert server.head() == before                      # working tree untouched
    assert not (server.app / "BREAK_TESTS").exists()
    calls = server.calls()
    assert "restart" not in calls                       # the running bot is left alone
    assert calls[0].startswith("notify: ⚠️ Déploiement annulé") and "tests en échec" in calls[0]


def test_service_that_does_not_stay_up_is_rolled_back(server):
    before = server.head()
    server.release("crashes at startup", BROKEN="x")
    result = server.deploy()
    assert result.returncode == 1
    assert server.head() == before                      # rolled back
    assert not (server.app / "BROKEN").exists()
    calls = server.calls()
    assert calls[:2] == ["restart", "restart"]          # new version, then the old one again
    assert calls[2].startswith("notify: ↩️ Retour à la version")
    assert server.service_state.read_text().strip() == "active"


def test_local_modifications_abort_the_deployment(server):
    server.release("v2", VERSION="2\n")
    (server.app / "VERSION").write_text("hand edited\n")
    result = server.deploy()
    assert result.returncode == 1
    assert (server.app / "VERSION").read_text() == "hand edited\n"
    assert "restart" not in server.calls()
    assert "modifications locales" in server.calls()[0]


def test_server_not_on_the_deployed_branch_aborts(server):
    git(server.app, "checkout", "-q", "--detach")
    server.release("v2", VERSION="2\n")
    assert server.deploy().returncode == 1
    assert "branche master" in server.calls()[0]


def test_server_ahead_of_origin_deploys_nothing(server):
    (server.app / "VERSION").write_text("local\n")
    git(server.app, "commit", "-q", "-am", "local commit")
    assert server.deploy().returncode == 0
    assert server.calls() == []


def test_diverged_history_aborts(server):
    (server.app / "LOCAL").write_text("x")
    git(server.app, "add", "-A")
    git(server.app, "commit", "-q", "-m", "local only")
    server.release("v2", VERSION="2\n")
    assert server.deploy().returncode == 1
    assert "divergé" in server.calls()[0]


def test_concurrent_deployment_is_skipped(server):
    server.release("v2", VERSION="2\n")
    with open(server.app / ".deploy.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = server.deploy()
    assert result.returncode == 0
    assert "Another deployment is running" in result.stdout
    assert server.calls() == []


def test_install_renders_units_and_a_narrow_sudo_rule(tmp_path):
    units, sudoers = tmp_path / "units", tmp_path / "sudoers"
    units.mkdir(), sudoers.mkdir()
    env = {**os.environ, "NO_SYSTEMD": "1", "UNIT_DIR": str(units), "SUDOERS_DIR": str(sudoers),
           "APP_USER": "opc", "SERVICE": "mybot"}
    subprocess.run([str(REPO / "deploy" / "install.sh")], env=env, check=True, capture_output=True)
    service = (units / "fondamentalnewsbot-deploy.service").read_text()
    assert f"ExecStart={REPO}/deploy/deploy.sh" in service
    assert "User=opc" in service and "Environment=SERVICE=mybot" in service
    assert "@" not in service
    assert "OnCalendar=" in (units / "fondamentalnewsbot-deploy.timer").read_text()
    rule = (sudoers / "fondamentalnewsbot-deploy").read_text().strip()
    assert rule.startswith("opc ALL=(root) NOPASSWD: ") and rule.endswith(" restart mybot")


def test_notify_posts_to_the_alert_chat(tmp_path, monkeypatch):
    received = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            received["path"] = self.path
            received["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *args):
            pass

    httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    config = tmp_path / "config.yaml"
    config.write_text("telegram:\n  token: '123:abc'\n  alert_chat_id: 42\n")
    monkeypatch.setenv("CONFIG", str(config))
    monkeypatch.setenv("TELEGRAM_API_URL", f"http://127.0.0.1:{httpd.server_port}")
    spec = importlib.util.spec_from_file_location("notify", REPO / "deploy" / "notify.py")
    notify = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(notify)
    try:
        assert notify.send("🚀 Déployé") is True
    finally:
        httpd.shutdown()
    assert received["path"] == "/bot123:abc/sendMessage"
    assert received["body"] == {"chat_id": 42, "text": "🚀 Déployé"}

    config.write_text("telegram:\n  token: '123:abc'\n")  # no alert chat: nothing to send
    assert notify.send("x") is False
