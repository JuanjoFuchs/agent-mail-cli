"""Agent mailbox — agent-to-agent messaging for local coding agents.

SQLite-backed, zero external dependencies. Ephemeral messages with a fixed 24h TTL.

Usage:
    agent-mail describe                                                Print CLI schema
    agent-mail describe send                                           Schema for one command
    agent-mail send --from second-brain:main --to claudefana:deploy --subject "fix X"
    agent-mail send --from a:b --to c:d --subject "X" --body-file body.md
    agent-mail send --from second-brain:main --to "*" --subject "status check"
    agent-mail read claudefana:deploy                                  Read unread inbox
    agent-mail read claudefana:deploy --all --limit 50                 Read all messages
    agent-mail read claudefana:deploy --fields id,sender,subject       Project specific fields
    agent-mail ack claudefana:deploy <uuid>                            Acknowledge a message
    agent-mail status                                                  Show all agents + counts
    agent-mail cleanup --dry-run                                       Preview expired purge

All commands output JSON on stdout. Errors are JSON on stderr with non-zero exit.
Agent identity format: project:name (e.g. claudefana:deploy, second-brain:main).
No registration needed — just send and read. Recipients don't need to exist yet.
DB location: ~/.agent-mail/mail.db (override with AGENT_MAIL_DB env var).
"""

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys
import uuid
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".agent-mail" / "mail.db"
TTL_HOURS = 24

# --- Schema (Pattern 2: Schema Introspection Replaces Documentation) ---

SCHEMA = {
    "name": "agent-mail",
    "description": "Agent-to-agent mailbox for local coding agents. SQLite-backed, zero external deps.",
    "usage": "agent-mail <command> [args]",
    "storage": f"{DEFAULT_DB_PATH} (override with AGENT_MAIL_DB env var)",
    "agent_identity": {
        "format": "project:name",
        "examples": ["second-brain:main", "claudefana:deploy", "tranzact:worker-1"],
        "rule": "project is the repo/project name, name is the session/agent name. Both lowercase alphanumeric + hyphens.",
    },
    "content_routing": {
        "messages": "Ephemeral coordination — status updates, prompts, acks, handoffs. Auto-expires via TTL. This is what agent-mail handles.",
        "vault_files": "Personal persistent knowledge — strategy, cross-project context, learnings. Agents write files directly to the Obsidian vault. Survives beyond any single task.",
        "repo_files": "Shared persistent implementation — specs, docs, architecture decisions. Agents write files directly to project repos. Readable by other maintainers/users.",
        "rule": "If it should outlive the current task, it's a file, not a message. Messages reference files via --refs but don't manage them.",
    },
    "invariants": [
        "All output is JSON on stdout, pretty-printed with two-space indentation",
        "All errors are JSON on stderr with 'error' key and non-zero exit code",
        "Messages are ephemeral — fixed 24h TTL, auto-cleanup on send/read/status",
        "Agent identity: project:name (e.g. claudefana:deploy, second-brain:main)",
        "Broadcast: use --to '*' — all agents see it",
        "File references in --refs are paths relative to sender's project root",
        "No registration needed — recipients don't need to exist before sending",
        "DB auto-creates on first use — no setup step required",
        "Long bodies with code/markdown: use --body-file to avoid shell escaping",
    ],
    "commands": {
        "describe": {
            "description": "Print this schema as JSON. No DB required.",
            "args": {
                "command": {"type": "str", "positional": True, "required": False,
                            "description": "Show schema for a specific command only"},
            },
            "examples": ["describe", "describe send"],
        },
        "send": {
            "description": "Send a message to another agent (or broadcast to all with --to '*'). Recipient doesn't need to exist yet.",
            "mutating": True,
            "args": {
                "--from": {"type": "str", "required": True,
                           "description": "Sender identity (project:name)"},
                "--to": {"type": "str", "required": True,
                         "description": "Recipient identity (project:name), or '*' for broadcast"},
                "--subject": {"type": "str", "required": True, "description": "Message subject line"},
                "--body": {"type": "str", "required": False,
                           "description": "Message body text. Mutually exclusive with --body-file."},
                "--body-file": {"type": "str", "required": False,
                                "description": "Read message body from a UTF-8 file. Use this for long bodies, code blocks, or text that breaks shell escaping. Mutually exclusive with --body."},
                "--refs": {"type": "str", "required": False,
                           "description": "JSON array of file paths referenced by this message"},
                "--reply-to": {"type": "str", "required": False,
                               "description": "Message ID (UUID) to reply to (creates thread)"},
            },
            "output_fields": ["id", "sender", "recipient", "subject", "type", "created", "ttl_hours"],
            "examples": [
                'send --from second-brain:main --to claudefana:deploy --subject "Fix the deploy bug" --body "See logs." --refs \'["logs/deploy-error.txt"]\'',
                'send --from second-brain:main --to claudefana:deploy --subject "Long write-up" --body-file /tmp/writeup.md',
                'send --from second-brain:main --to "*" --subject "Status check" --body "Report your current status."',
                'send --from claudefana:deploy --to second-brain:main --subject "Deploy fixed" --reply-to abc123-...',
            ],
        },
        "read": {
            "description": "Read inbox for an agent (unread messages by default). No registration needed.",
            "mutating": False,
            "args": {
                "agent": {"type": "str", "positional": True, "required": True,
                          "description": "Agent identity (project:name) to read inbox for"},
                "--all": {"type": "bool", "default": False,
                          "description": "Include already-read messages"},
                "--from": {"type": "str", "required": False,
                           "description": "Filter by sender identity"},
                "--limit": {"type": "int", "default": 20,
                            "description": "Max messages to return"},
                "--thread": {"type": "str", "required": False,
                             "description": "Show full thread for this message ID"},
                "--no-mark-read": {"type": "bool", "default": False,
                                   "description": "Don't mark returned messages as read"},
                "--fields": {"type": "str", "required": False,
                             "description": "Comma-separated subset of output_fields to include in each result. Saves agent context when only some fields are needed."},
            },
            "output_fields": ["id", "sender", "recipient", "subject", "body", "refs", "reply_to",
                               "type", "created", "ttl_hours", "read_at", "acked_at"],
            "examples": [
                "read claudefana:deploy",
                "read claudefana:deploy --all --limit 50",
                "read claudefana:deploy --from second-brain:main",
                "read second-brain:main --thread abc123-...",
                "read claudefana:deploy --fields id,sender,subject",
            ],
        },
        "ack": {
            "description": "Acknowledge a message (mark as acted upon). Distinct from read — 'I've done something about this.'",
            "mutating": True,
            "args": {
                "agent": {"type": "str", "positional": True, "required": True,
                          "description": "Agent identity (project:name) acknowledging the message"},
                "message_id": {"type": "str", "positional": True, "required": True,
                               "description": "UUID4 message ID to acknowledge"},
            },
            "output_fields": ["message_id", "agent", "acked_at"],
            "examples": ["ack claudefana:deploy 9f1c2e34-5678-4abc-9def-0123456789ab"],
        },
        "status": {
            "description": "Show all known agents and their unread/unacked message counts. Derived from message traffic — no registration needed.",
            "mutating": False,
            "args": {
                "--agent": {"type": "str", "required": False,
                            "description": "Show status for a specific agent identity only"},
                "--project": {"type": "str", "required": False,
                              "description": "Filter agents by project prefix"},
                "--fields": {"type": "str", "required": False,
                             "description": "Comma-separated subset of output_fields to include in each result."},
            },
            "output_fields": ["agent", "unread", "unacked"],
            "examples": [
                "status",
                "status --agent claudefana:deploy",
                "status --project claudefana",
                "status --fields agent,unread",
            ],
        },
        "cleanup": {
            "description": "Purge expired messages (TTL exceeded).",
            "mutating": True,
            "args": {
                "--dry-run": {"type": "bool", "default": False,
                              "description": "Show what would be deleted without deleting"},
            },
            "output_fields": ["deleted_count", "oldest_deleted", "newest_deleted"],
            "examples": ["cleanup", "cleanup --dry-run"],
        },
    },
}


# --- Input Validation (Pattern 4: Hardening Against Hallucinations) ---

# project:name — both parts: lowercase alphanumeric + hyphens, start with alphanumeric
AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*$")

# RFC 4122 UUID4 format (case-insensitive)
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def error(msg):
    """Print JSON error to stderr and exit."""
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


def validate_agent_id(value):
    if not AGENT_ID_RE.match(value):
        error(f"Invalid agent identity: {value!r}. Must be project:name format (e.g. claudefana:deploy).")
    return value


def validate_uuid(value):
    """Reject hallucinated message ids early — must look like a UUID before we hit the DB."""
    if not UUID_RE.match(value):
        error(f"Invalid message id: {value!r}. Must be a UUID (8-4-4-4-12 hex).")
    return value


def validate_refs(refs_str):
    """Parse and validate --refs JSON array."""
    try:
        refs = json.loads(refs_str)
    except json.JSONDecodeError:
        error(f"Invalid --refs JSON: {refs_str!r}. Expected JSON array of strings.")
    if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
        error(f"--refs must be a JSON array of strings, got: {refs_str!r}")
    return json.dumps(refs)


def validate_text(value):
    """Reject control characters in text input."""
    if any(ord(c) < 0x20 and c not in "\n\r\t" for c in value):
        error("Text contains invalid control characters.")
    return value


def read_body_file(path):
    """Read message body from file as UTF-8 text. Errors via error()."""
    p = Path(path)
    if not p.exists():
        error(f"--body-file not found: {path}")
    if not p.is_file():
        error(f"--body-file is not a regular file: {path}")
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        error(f"--body-file is not valid UTF-8: {path}")
    except OSError as e:
        error(f"Cannot read --body-file {path}: {e}")


def parse_fields(value, valid_fields):
    """Parse a --fields comma list and validate against valid_fields. Returns None if no projection."""
    if not value:
        return None
    fields = [f.strip() for f in value.split(",") if f.strip()]
    if not fields:
        return None
    invalid = [f for f in fields if f not in valid_fields]
    if invalid:
        error(f"Unknown --fields: {invalid}. Valid for this command: {sorted(valid_fields)}")
    return fields


def project_fields(item, fields):
    """Project a dict to a subset of keys, or pass through if fields is None."""
    if not fields:
        return item
    return {f: item.get(f) for f in fields}


# --- Database ---

def get_db_path():
    path = os.environ.get("AGENT_MAIL_DB")
    if path:
        return Path(path)
    return DEFAULT_DB_PATH


def get_db():
    """Open DB connection, create tables if needed."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_db(conn)
    return conn


def _init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id          TEXT PRIMARY KEY,
            sender      TEXT NOT NULL,
            recipient   TEXT NOT NULL,
            subject     TEXT NOT NULL,
            body        TEXT NOT NULL DEFAULT '',
            refs        TEXT,
            reply_to    TEXT,
            type        TEXT NOT NULL DEFAULT 'direct',
            ttl_hours   INTEGER NOT NULL DEFAULT 24,
            created     TEXT NOT NULL,
            read_at     TEXT,
            acked_at    TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient);
        CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender);
        CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created);

        CREATE TABLE IF NOT EXISTS broadcast_acks (
            message_id  TEXT NOT NULL,
            agent       TEXT NOT NULL,
            read_at     TEXT,
            acked_at    TEXT,
            PRIMARY KEY (message_id, agent)
        );
    """)


def _now_iso():
    return datetime.datetime.now().astimezone().isoformat()


def _cleanup_expired(conn):
    """Opportunistic cleanup of expired messages."""
    now = datetime.datetime.now().astimezone()
    rows = conn.execute("SELECT id, created, ttl_hours FROM messages").fetchall()
    expired_ids = []
    for row in rows:
        created = datetime.datetime.fromisoformat(row["created"])
        if now > created + datetime.timedelta(hours=row["ttl_hours"]):
            expired_ids.append(row["id"])
    if expired_ids:
        placeholders = ",".join("?" for _ in expired_ids)
        conn.execute(f"DELETE FROM broadcast_acks WHERE message_id IN ({placeholders})", expired_ids)
        conn.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", expired_ids)
        conn.commit()
    return len(expired_ids)


def _discover_agents(conn):
    """Derive known agents from message traffic (senders + recipients)."""
    rows = conn.execute("""
        SELECT DISTINCT agent FROM (
            SELECT sender AS agent FROM messages
            UNION
            SELECT recipient AS agent FROM messages WHERE recipient != '*'
        )
        ORDER BY agent
    """).fetchall()
    return [row["agent"] for row in rows]


# --- Output ---

def output(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


# --- Commands ---

def cmd_describe(desc_command):
    """Print full schema or a single command's schema."""
    if desc_command:
        cmd_schema = SCHEMA["commands"].get(desc_command)
        if not cmd_schema:
            error(f"Unknown command: {desc_command!r}. Available: {', '.join(SCHEMA['commands'].keys())}")
        output({desc_command: cmd_schema})
    else:
        output(SCHEMA)


def cmd_send(args):
    """Send a message from one agent to another."""
    sender = validate_agent_id(getattr(args, "from"))
    recipient = args.to
    if recipient != "*":
        validate_agent_id(recipient)
    subject = validate_text(args.subject)

    # Body: --body or --body-file (mutually exclusive). --body-file solves shell-escaping
    # failures on long bodies with code blocks, markdown, or special characters.
    if args.body is not None and args.body_file is not None:
        error("Cannot use both --body and --body-file. Choose one.")
    if args.body_file is not None:
        body = validate_text(read_body_file(args.body_file))
    elif args.body is not None:
        body = validate_text(args.body)
    else:
        body = ""

    refs = validate_refs(args.refs) if args.refs else None
    reply_to = args.reply_to
    if reply_to is not None:
        validate_uuid(reply_to)

    conn = get_db()
    _cleanup_expired(conn)

    msg_id = str(uuid.uuid4())
    msg_type = "broadcast" if recipient == "*" else "direct"
    now = _now_iso()

    conn.execute(
        """INSERT INTO messages (id, sender, recipient, subject, body, refs, reply_to, type, ttl_hours, created)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (msg_id, sender, recipient, subject, body, refs, reply_to, msg_type, TTL_HOURS, now),
    )
    conn.commit()

    output({
        "id": msg_id,
        "sender": sender,
        "recipient": recipient,
        "subject": subject,
        "type": msg_type,
        "created": now,
        "ttl_hours": TTL_HOURS,
    })


def cmd_read(args):
    """Read inbox for an agent."""
    agent = validate_agent_id(args.agent)

    valid_fields = SCHEMA["commands"]["read"]["output_fields"]
    fields = parse_fields(args.fields, valid_fields)

    conn = get_db()
    _cleanup_expired(conn)

    mark_read = not args.no_mark_read

    # Thread mode: show full thread, never marks read.
    if args.thread:
        validate_uuid(args.thread)
        messages = _get_thread(conn, args.thread)
        results = [project_fields(dict(row), fields) for row in messages]
        output(results)
        return

    if args.all:
        query = """
            SELECT * FROM messages
            WHERE (recipient = ? OR recipient = '*')
              AND sender != ?
        """
        params = [agent, agent]
    else:
        query = """
            SELECT * FROM messages
            WHERE sender != ?
              AND (
                (recipient = ? AND read_at IS NULL)
                OR
                (recipient = '*' AND NOT EXISTS (
                  SELECT 1 FROM broadcast_acks ba
                  WHERE ba.message_id = messages.id AND ba.agent = ? AND ba.read_at IS NOT NULL
                ))
              )
        """
        params = [agent, agent, agent]

    if getattr(args, "from"):
        validate_agent_id(getattr(args, "from"))
        query += " AND sender = ?"
        params.append(getattr(args, "from"))

    query += " ORDER BY created ASC LIMIT ?"
    params.append(args.limit)

    rows = conn.execute(query, params).fetchall()
    raw_results = [dict(row) for row in rows]

    # Mark as read (must run before projection so we still have id + recipient available).
    if mark_read and raw_results:
        now = _now_iso()
        for msg in raw_results:
            if msg["recipient"] == "*":
                conn.execute(
                    """INSERT INTO broadcast_acks (message_id, agent, read_at)
                       VALUES (?, ?, ?)
                       ON CONFLICT(message_id, agent) DO UPDATE SET read_at = ?""",
                    (msg["id"], agent, now, now),
                )
            else:
                if not msg["read_at"]:
                    conn.execute("UPDATE messages SET read_at = ? WHERE id = ?", (now, msg["id"]))
        conn.commit()

    results = [project_fields(msg, fields) for msg in raw_results]
    output(results)


def _get_thread(conn, message_id):
    """Reconstruct a thread from any message in it."""
    root_id = message_id
    seen = set()
    while root_id and root_id not in seen:
        seen.add(root_id)
        row = conn.execute("SELECT reply_to FROM messages WHERE id = ?", (root_id,)).fetchone()
        if not row or not row["reply_to"]:
            break
        root_id = row["reply_to"]

    return conn.execute("""
        WITH RECURSIVE thread(id) AS (
            SELECT ?
            UNION ALL
            SELECT m.id FROM messages m JOIN thread t ON m.reply_to = t.id
        )
        SELECT m.* FROM messages m JOIN thread t ON m.id = t.id ORDER BY m.created ASC
    """, (root_id,)).fetchall()


def cmd_ack(args):
    """Acknowledge a message."""
    agent = validate_agent_id(args.agent)
    msg_id = validate_uuid(args.message_id)

    conn = get_db()
    msg = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
    if not msg:
        error(f"Message not found: {msg_id}")

    now = _now_iso()

    if msg["recipient"] == "*":
        conn.execute(
            """INSERT INTO broadcast_acks (message_id, agent, acked_at)
               VALUES (?, ?, ?)
               ON CONFLICT(message_id, agent) DO UPDATE SET acked_at = ?""",
            (msg_id, agent, now, now),
        )
    else:
        conn.execute("UPDATE messages SET acked_at = ? WHERE id = ?", (now, msg_id))
    conn.commit()

    output({"message_id": msg_id, "agent": agent, "acked_at": now})


def cmd_status(args):
    """Show all known agents and unread/unacked counts. Derived from message traffic."""
    valid_fields = SCHEMA["commands"]["status"]["output_fields"]
    fields = parse_fields(args.fields, valid_fields)

    conn = get_db()
    _cleanup_expired(conn)

    agents = _discover_agents(conn)

    # Apply filters
    if args.agent:
        validate_agent_id(args.agent)
        agents = [a for a in agents if a == args.agent]
    elif args.project:
        prefix = args.project + ":"
        agents = [a for a in agents if a.startswith(prefix)]

    raw_results = []
    for agent in agents:
        # Unread direct
        unread_direct = conn.execute(
            "SELECT COUNT(*) as c FROM messages WHERE recipient = ? AND read_at IS NULL AND sender != ?",
            (agent, agent),
        ).fetchone()["c"]

        # Unread broadcasts
        unread_broadcast = conn.execute("""
            SELECT COUNT(*) as c FROM messages m
            WHERE m.recipient = '*' AND m.sender != ?
              AND NOT EXISTS (
                SELECT 1 FROM broadcast_acks ba
                WHERE ba.message_id = m.id AND ba.agent = ? AND ba.read_at IS NOT NULL
              )
        """, (agent, agent)).fetchone()["c"]

        # Unacked direct
        unacked_direct = conn.execute(
            "SELECT COUNT(*) as c FROM messages WHERE recipient = ? AND acked_at IS NULL AND sender != ?",
            (agent, agent),
        ).fetchone()["c"]

        # Unacked broadcasts
        unacked_broadcast = conn.execute("""
            SELECT COUNT(*) as c FROM messages m
            WHERE m.recipient = '*' AND m.sender != ?
              AND NOT EXISTS (
                SELECT 1 FROM broadcast_acks ba
                WHERE ba.message_id = m.id AND ba.agent = ? AND ba.acked_at IS NOT NULL
              )
        """, (agent, agent)).fetchone()["c"]

        raw_results.append({
            "agent": agent,
            "unread": unread_direct + unread_broadcast,
            "unacked": unacked_direct + unacked_broadcast,
        })

    results = [project_fields(r, fields) for r in raw_results]
    output(results)


def cmd_cleanup(args):
    """Purge expired messages."""
    conn = get_db()
    now = datetime.datetime.now().astimezone()
    dry_run = args.dry_run

    rows = conn.execute("SELECT id, sender, recipient, subject, created, ttl_hours FROM messages").fetchall()
    expired = []
    for row in rows:
        created = datetime.datetime.fromisoformat(row["created"])
        if now > created + datetime.timedelta(hours=row["ttl_hours"]):
            expired.append(dict(row))

    if not expired:
        output({"deleted_count": 0})
        return

    if dry_run:
        output({
            "dry_run": True,
            "would_delete": len(expired),
            "oldest": expired[0]["created"],
            "newest": expired[-1]["created"],
            "messages": [{"id": m["id"], "sender": m["sender"], "subject": m["subject"]} for m in expired],
        })
        return

    expired_ids = [m["id"] for m in expired]
    placeholders = ",".join("?" for _ in expired_ids)
    conn.execute(f"DELETE FROM broadcast_acks WHERE message_id IN ({placeholders})", expired_ids)
    conn.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", expired_ids)
    conn.commit()

    output({
        "deleted_count": len(expired_ids),
        "oldest_deleted": expired[0]["created"],
        "newest_deleted": expired[-1]["created"],
    })


# --- CLI ---

def build_parser():
    parser = argparse.ArgumentParser(description="Agent mailbox for local coding agents.")
    sub = parser.add_subparsers(dest="command")

    # describe
    p = sub.add_parser("describe", help="Print CLI schema as JSON")
    p.add_argument("desc_command", nargs="?", metavar="command", help="Show schema for specific command")

    # send
    p = sub.add_parser("send", help="Send a message")
    p.add_argument("--from", required=True, dest="from", help="Sender (project:name)")
    p.add_argument("--to", required=True, help="Recipient (project:name) or '*' for broadcast")
    p.add_argument("--subject", required=True, help="Message subject")
    p.add_argument("--body", default=None, help="Message body (mutually exclusive with --body-file)")
    p.add_argument("--body-file", default=None, dest="body_file",
                   help="Read body from UTF-8 file (mutually exclusive with --body)")
    p.add_argument("--refs", help="JSON array of file path references")
    p.add_argument("--reply-to", dest="reply_to", help="Message UUID to reply to")

    # read
    p = sub.add_parser("read", help="Read inbox")
    p.add_argument("agent", help="Agent identity (project:name)")
    p.add_argument("--all", action="store_true", help="Include read messages")
    p.add_argument("--from", dest="from", help="Filter by sender")
    p.add_argument("--limit", type=int, default=20, help="Max messages (default: 20)")
    p.add_argument("--thread", help="Show thread for message UUID")
    p.add_argument("--no-mark-read", action="store_true", dest="no_mark_read", help="Don't mark as read")
    p.add_argument("--fields", help="Comma-separated subset of output_fields")

    # ack
    p = sub.add_parser("ack", help="Acknowledge a message")
    p.add_argument("agent", help="Agent identity (project:name)")
    p.add_argument("message_id", help="Message UUID")

    # status
    p = sub.add_parser("status", help="Show agent status")
    p.add_argument("--agent", help="Specific agent identity")
    p.add_argument("--project", help="Filter by project prefix")
    p.add_argument("--fields", help="Comma-separated subset of output_fields")

    # cleanup
    p = sub.add_parser("cleanup", help="Purge expired messages")
    p.add_argument("--dry-run", action="store_true", dest="dry_run", help="Preview without deleting")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        if not args.command:
            cmd_describe(None)
            return
        if args.command == "describe":
            cmd_describe(getattr(args, "desc_command", None))
        elif args.command == "send":
            cmd_send(args)
        elif args.command == "read":
            cmd_read(args)
        elif args.command == "ack":
            cmd_ack(args)
        elif args.command == "status":
            cmd_status(args)
        elif args.command == "cleanup":
            cmd_cleanup(args)
        else:
            error(f"Unknown command: {args.command}. Run 'describe' for usage.")
    except SystemExit:
        raise
    except Exception as e:
        error(str(e))


if __name__ == "__main__":
    main()
