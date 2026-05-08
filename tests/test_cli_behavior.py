import datetime as dt
import json
import uuid

from conftest import db_connect


def test_describe_schema_variants_do_not_require_db(run_cli, db_path):
    full = run_cli(["describe"]).json
    implicit = run_cli([]).json
    assert implicit == full
    assert {"name", "description", "usage", "storage", "agent_identity", "content_routing", "invariants", "commands"} <= set(full)
    assert full["name"] == "agent-mail"
    assert "agent-mail <command>" in full["usage"]
    assert not db_path.exists()

    for command in ["describe", "send", "read", "ack", "status", "cleanup"]:
        one = run_cli(["describe", command]).json
        assert list(one) == [command]
        assert one[command] == full["commands"][command]


def test_send_direct_broadcast_refs_reply_and_body_file(run_cli, db_path, tmp_path):
    body_path = tmp_path / "body.md"
    body_text = "Line 1\n```python\nprint('x')\n```\n"
    body_path.write_text(body_text, encoding="utf-8")

    direct = run_cli([
        "send",
        "--from",
        "proj:sender",
        "--to",
        "proj:receiver",
        "--subject",
        "Hello",
        "--body-file",
        str(body_path),
        "--refs",
        '["a","b"]',
    ]).json
    assert direct["sender"] == "proj:sender"
    assert direct["recipient"] == "proj:receiver"
    assert direct["subject"] == "Hello"
    assert direct["type"] == "direct"
    assert direct["ttl_hours"] == 24
    uuid.UUID(direct["id"], version=4)
    dt.datetime.fromisoformat(direct["created"])

    broadcast = run_cli([
        "send",
        "--from",
        "proj:sender",
        "--to",
        "*",
        "--subject",
        "Broadcast",
    ]).json
    assert broadcast["type"] == "broadcast"

    reply = run_cli([
        "send",
        "--from",
        "proj:receiver",
        "--to",
        "proj:sender",
        "--subject",
        "Re",
        "--reply-to",
        direct["id"],
    ]).json
    assert reply["type"] == "direct"

    read = run_cli(["read", "proj:receiver", "--all", "--no-mark-read"]).json
    by_id = {m["id"]: m for m in read}
    assert by_id[direct["id"]]["body"] == body_text
    assert by_id[direct["id"]]["refs"] == '["a", "b"]'

    with db_connect(db_path) as conn:
        row = conn.execute("SELECT reply_to, ttl_hours FROM messages WHERE id = ?", (reply["id"],)).fetchone()
    assert row["reply_to"] == direct["id"]
    assert row["ttl_hours"] == 24


def test_send_validation_errors_are_json_and_do_not_insert(run_cli, db_path, tmp_path):
    body_path = tmp_path / "body.txt"
    body_path.write_text("body", encoding="utf-8")
    non_utf8 = tmp_path / "bad.bin"
    non_utf8.write_bytes(b"\xff\xfe")

    cases = [
        ["send", "--from", "bad", "--to", "proj:receiver", "--subject", "x"],
        ["send", "--from", "proj:sender", "--to", "bad", "--subject", "x"],
        ["send", "--from", "proj:sender", "--to", "proj:receiver", "--subject", "bad\x01"],
        ["send", "--from", "proj:sender", "--to", "proj:receiver", "--subject", "x", "--refs", "nope"],
        ["send", "--from", "proj:sender", "--to", "proj:receiver", "--subject", "x", "--reply-to", "not-a-uuid"],
        ["send", "--from", "proj:sender", "--to", "proj:receiver", "--subject", "x", "--body", "a", "--body-file", str(body_path)],
        ["send", "--from", "proj:sender", "--to", "proj:receiver", "--subject", "x", "--body-file", str(tmp_path / "missing")],
        ["send", "--from", "proj:sender", "--to", "proj:receiver", "--subject", "x", "--body-file", str(non_utf8)],
    ]
    for args in cases:
        result = run_cli(args, check=False)
        assert result.code != 0
        assert "error" in result.error_json

    if db_path.exists():
        with db_connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"]
        assert count == 0


def test_read_filters_mark_read_thread_and_fields(run_cli, db_path):
    first = run_cli([
        "send",
        "--from",
        "proj:sender",
        "--to",
        "proj:receiver",
        "--subject",
        "first",
        "--body",
        "body",
    ]).json
    second = run_cli([
        "send",
        "--from",
        "proj:other",
        "--to",
        "proj:receiver",
        "--subject",
        "second",
    ]).json
    broadcast = run_cli([
        "send",
        "--from",
        "proj:sender",
        "--to",
        "*",
        "--subject",
        "broadcast",
    ]).json
    self_sent = run_cli([
        "send",
        "--from",
        "proj:receiver",
        "--to",
        "proj:receiver",
        "--subject",
        "self",
    ]).json

    preview = run_cli(["read", "proj:receiver", "--no-mark-read"]).json
    preview_ids = {m["id"] for m in preview}
    assert {first["id"], second["id"], broadcast["id"]} <= preview_ids
    assert self_sent["id"] not in preview_ids

    again = run_cli(["read", "proj:receiver"]).json
    assert {first["id"], second["id"], broadcast["id"]} <= {m["id"] for m in again}
    assert run_cli(["read", "proj:receiver"]).json == []

    all_messages = run_cli(["read", "proj:receiver", "--all"]).json
    assert {first["id"], second["id"], broadcast["id"]} <= {m["id"] for m in all_messages}

    filtered = run_cli(["read", "proj:receiver", "--all", "--from", "proj:other"]).json
    assert [m["id"] for m in filtered] == [second["id"]]

    limited = run_cli(["read", "proj:receiver", "--all", "--limit", "1"]).json
    assert len(limited) == 1

    projected = run_cli(["read", "proj:receiver", "--all", "--fields", "id,sender,subject"]).json
    assert projected
    assert list(projected[0]) == ["id", "sender", "subject"]

    bad_fields = run_cli(["read", "proj:receiver", "--fields", "nope"], check=False)
    assert bad_fields.code != 0
    assert "Unknown --fields" in bad_fields.error_json["error"]

    child = run_cli([
        "send",
        "--from",
        "proj:receiver",
        "--to",
        "proj:sender",
        "--subject",
        "reply",
        "--reply-to",
        first["id"],
    ]).json
    thread = run_cli(["read", "proj:receiver", "--thread", child["id"]]).json
    assert [m["id"] for m in thread] == [first["id"], child["id"]]

    bad_thread = run_cli(["read", "proj:receiver", "--thread", "not-a-uuid"], check=False)
    assert bad_thread.code != 0
    assert "error" in bad_thread.error_json


def test_read_marks_direct_and_broadcast_in_expected_tables(run_cli, db_path):
    direct = run_cli([
        "send",
        "--from",
        "proj:sender",
        "--to",
        "proj:receiver",
        "--subject",
        "direct",
    ]).json
    broadcast = run_cli([
        "send",
        "--from",
        "proj:sender",
        "--to",
        "*",
        "--subject",
        "broadcast",
    ]).json
    run_cli(["read", "proj:receiver"])

    with db_connect(db_path) as conn:
        direct_row = conn.execute("SELECT read_at FROM messages WHERE id = ?", (direct["id"],)).fetchone()
        broadcast_row = conn.execute(
            "SELECT read_at FROM broadcast_acks WHERE message_id = ? AND agent = ?",
            (broadcast["id"], "proj:receiver"),
        ).fetchone()
    assert direct_row["read_at"]
    assert broadcast_row["read_at"]


def test_ack_direct_broadcast_and_errors(run_cli, db_path):
    direct = run_cli([
        "send",
        "--from",
        "proj:sender",
        "--to",
        "proj:receiver",
        "--subject",
        "direct",
    ]).json
    broadcast = run_cli([
        "send",
        "--from",
        "proj:sender",
        "--to",
        "*",
        "--subject",
        "broadcast",
    ]).json

    direct_ack = run_cli(["ack", "proj:receiver", direct["id"]]).json
    broadcast_ack = run_cli(["ack", "proj:other", broadcast["id"]]).json
    assert direct_ack["message_id"] == direct["id"]
    assert broadcast_ack["agent"] == "proj:other"

    with db_connect(db_path) as conn:
        direct_row = conn.execute("SELECT acked_at FROM messages WHERE id = ?", (direct["id"],)).fetchone()
        broadcast_row = conn.execute(
            "SELECT acked_at FROM broadcast_acks WHERE message_id = ? AND agent = ?",
            (broadcast["id"], "proj:other"),
        ).fetchone()
    assert direct_row["acked_at"]
    assert broadcast_row["acked_at"]

    bad_uuid = run_cli(["ack", "proj:receiver", "not-a-uuid"], check=False)
    assert bad_uuid.code != 0
    assert "error" in bad_uuid.error_json

    missing = run_cli(["ack", "proj:receiver", str(uuid.uuid4())], check=False)
    assert missing.code != 0
    assert "Message not found" in missing.error_json["error"]


def test_status_filters_fields_counts_and_errors(run_cli):
    run_cli(["send", "--from", "proj:a", "--to", "proj:b", "--subject", "direct"])
    run_cli(["send", "--from", "proj:a", "--to", "*", "--subject", "broadcast"])
    run_cli(["send", "--from", "other:a", "--to", "proj:a", "--subject", "incoming"])

    status = run_cli(["status"]).json
    by_agent = {row["agent"]: row for row in status}
    assert by_agent["proj:b"]["unread"] == 2
    assert by_agent["proj:b"]["unacked"] == 2
    assert by_agent["proj:a"]["unread"] == 1

    one = run_cli(["status", "--agent", "proj:b"]).json
    assert [row["agent"] for row in one] == ["proj:b"]

    project = run_cli(["status", "--project", "proj"]).json
    assert {row["agent"] for row in project} == {"proj:a", "proj:b"}

    fields = run_cli(["status", "--fields", "agent,unread"]).json
    assert fields
    assert list(fields[0]) == ["agent", "unread"]

    bad_fields = run_cli(["status", "--fields", "nope"], check=False)
    assert bad_fields.code != 0
    assert "error" in bad_fields.error_json


def test_cleanup_dry_run_real_run_and_opportunistic_cleanup(run_cli, db_path):
    old = run_cli(["send", "--from", "proj:a", "--to", "proj:b", "--subject", "old"]).json
    fresh = run_cli(["send", "--from", "proj:a", "--to", "proj:b", "--subject", "fresh"]).json
    old_created = (dt.datetime.now().astimezone() - dt.timedelta(hours=25)).isoformat()

    with db_connect(db_path) as conn:
        conn.execute("UPDATE messages SET created = ? WHERE id = ?", (old_created, old["id"]))
        conn.commit()

    dry = run_cli(["cleanup", "--dry-run"]).json
    assert dry["dry_run"] is True
    assert dry["would_delete"] == 1
    assert dry["messages"][0]["id"] == old["id"]

    real = run_cli(["cleanup"]).json
    assert real["deleted_count"] == 1
    with db_connect(db_path) as conn:
        remaining = {row["id"] for row in conn.execute("SELECT id FROM messages").fetchall()}
    assert remaining == {fresh["id"]}

    assert run_cli(["cleanup"]).json == {"deleted_count": 0}

    expired = run_cli(["send", "--from", "proj:a", "--to", "proj:b", "--subject", "expired"]).json
    with db_connect(db_path) as conn:
        conn.execute("UPDATE messages SET created = ? WHERE id = ?", (old_created, expired["id"]))
        conn.commit()
    run_cli(["status"])
    with db_connect(db_path) as conn:
        missing = conn.execute("SELECT id FROM messages WHERE id = ?", (expired["id"],)).fetchone()
    assert missing is None


def test_storage_override_schema_and_default_home_path(run_cli, db_path, tmp_path):
    override_db = tmp_path / "nested" / "override.db"
    run_cli(["send", "--from", "proj:a", "--to", "proj:b", "--subject", "override"], db=override_db)
    assert override_db.exists()
    assert not db_path.exists()

    with db_connect(override_db) as conn:
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        indexes = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert {"messages", "broadcast_acks"} <= tables
    assert {"idx_messages_recipient", "idx_messages_sender", "idx_messages_created"} <= indexes
    assert mode == "wal"

    fake_home = tmp_path / "home"
    run_cli(["send", "--from", "proj:a", "--to", "proj:b", "--subject", "default"], db=None, home=fake_home)
    assert (fake_home / ".agent-mail" / "mail.db").exists()


def test_success_output_and_application_errors_are_json(run_cli):
    ok = run_cli(["status"])
    assert ok.code == 0
    assert isinstance(json.loads(ok.stdout), list)

    err = run_cli(["describe", "missing"], check=False)
    assert err.code != 0
    assert "error" in json.loads(err.stderr)
