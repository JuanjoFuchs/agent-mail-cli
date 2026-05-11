import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass
class CliResult:
    code: int
    stdout: str
    stderr: str

    @property
    def json(self):
        assert self.stdout, "expected stdout JSON"
        return json.loads(self.stdout)

    @property
    def error_json(self):
        assert self.stderr, "expected stderr JSON"
        return json.loads(self.stderr)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "mail.db"


@pytest.fixture
def run_cli(db_path):
    default_db = object()
    default_runner = os.environ.get("AGENT_MAIL_RUNNER", "module")

    def _run(args, *, db=default_db, home=None, runner=None, check=True):
        runner = runner or default_runner
        env = os.environ.copy()
        if db is default_db:
            env["AGENT_MAIL_DB"] = str(db_path)
        elif db is not None:
            env["AGENT_MAIL_DB"] = str(db)
        else:
            env.pop("AGENT_MAIL_DB", None)
        if home is not None:
            env["HOME"] = str(home)
            env["USERPROFILE"] = str(home)

        if runner == "module":
            cmd = [sys.executable, "-m", "agent_mail", *args]
        elif runner == "binary":
            binary = os.environ.get("AGENT_MAIL_BINARY")
            if not binary:
                pytest.skip("AGENT_MAIL_BINARY is not set")
            cmd = [binary, *args]
        elif runner == "command":
            command = os.environ.get("AGENT_MAIL_COMMAND", "agent-mail")
            cmd = [command, *args]
        elif runner == "npm":
            wrapper = Path(
                os.environ.get(
                    "AGENT_MAIL_NPM_WRAPPER",
                    Path(__file__).resolve().parents[1] / "npm" / "bin" / "agent-mail.js",
                )
            )
            if not wrapper.exists():
                pytest.skip("npm wrapper is not available")
            if not any(wrapper.parent.glob("agent-mail-*")):
                pytest.skip("npm-downloaded agent-mail binary is not available")
            cmd = ["node", str(wrapper), *args]
        else:
            raise ValueError(f"unknown runner: {runner}")

        completed = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        result = CliResult(completed.returncode, completed.stdout, completed.stderr)
        if check and result.code != 0:
            raise AssertionError(
                f"command failed: {cmd}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        return result

    return _run


def db_connect(path: Path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn
