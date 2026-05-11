import json
import re

import pytest

DYNAMIC_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
DYNAMIC_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def normalize(value):
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, str):
        if DYNAMIC_UUID_RE.match(value):
            return "<uuid>"
        if DYNAMIC_ISO_RE.match(value):
            return "<timestamp>"
    return value


@pytest.mark.parametrize(
    "args,expect_error",
    [
        (["describe"], False),
        (["describe", "send"], False),
        (["describe", "missing"], True),
        (["send", "--from", "bad", "--to", "proj:b", "--subject", "x"], True),
        (["ack", "proj:a", "not-a-uuid"], True),
    ],
)
def test_module_pyinstaller_and_npm_parity(run_cli, tmp_path, args, expect_error):
    module_db = tmp_path / "module.db"
    binary_db = tmp_path / "binary.db"
    npm_db = tmp_path / "npm.db"

    module = run_cli(args, db=module_db, runner="module", check=False)
    binary = run_cli(args, db=binary_db, runner="binary", check=False)
    npm = run_cli(args, db=npm_db, runner="npm", check=False)

    assert binary.code == module.code
    assert npm.code == module.code
    if expect_error:
        assert normalize(json.loads(binary.stderr)) == normalize(json.loads(module.stderr))
        assert normalize(json.loads(npm.stderr)) == normalize(json.loads(module.stderr))
    else:
        assert normalize(json.loads(binary.stdout)) == normalize(json.loads(module.stdout))
        assert normalize(json.loads(npm.stdout)) == normalize(json.loads(module.stdout))
