"""Tests for restart_process: arguments of the exec, failure fallback, and a real re-exec."""

import os
import subprocess
import sys
import textwrap

import pytest

from bot import restart


def test_restart_reuses_interpreter_and_flags(monkeypatch):
    seen = {}
    monkeypatch.setattr(os, "execv", lambda path, argv: seen.update(path=path, argv=argv))
    monkeypatch.setattr(sys, "orig_argv", ["python", "-u", "main.py"])
    restart.restart_process()
    assert seen["path"] == sys.executable
    assert seen["argv"] == [sys.executable, "-u", "main.py"]


def test_failed_exec_exits_with_error_so_a_supervisor_restarts_the_bot(monkeypatch):
    def boom(path, argv):
        raise OSError("exec failed")

    monkeypatch.setattr(os, "execv", boom)
    with pytest.raises(SystemExit) as exc:
        restart.restart_process()
    assert exc.value.code == 1


def test_real_re_exec_runs_the_same_command_line_again(tmp_path):
    marker = tmp_path / "runs.txt"
    script = tmp_path / "app.py"
    script.write_text(textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {os.getcwd()!r})
        from bot.restart import restart_process
        with open({str(marker)!r}, "a") as f:
            f.write("run\\n")
        if open({str(marker)!r}).read().count("run") < 2:
            restart_process()
        print("done")
    """))
    out = subprocess.run([sys.executable, "-u", str(script)], capture_output=True, text=True, timeout=30,
                         cwd=tmp_path)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "done"
    assert marker.read_text().count("run") == 2  # started, re-exec'd once, then finished
