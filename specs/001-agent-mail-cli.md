---
id: "001"
title: Agent Mail v1 — Behavioral Specification
status: pending
mirrors: src/mail.py
blocked_by: []
blocks: ["002"]
---

# Agent Mail v1 — Behavioral Specification

## Overview

This is the retrospective specification for `mail.py`, a SQLite-backed agent-to-agent inbox built and used inside JJ's second-brain vault before this repo existed. It is the spec that should have been written when the script was built.

The script is the smallest useful messaging primitive between local coding agents: send, read, ack, status, cleanup, describe — JSON in, JSON out, no daemon, no registration, no MCP. It is currently the de facto coordination channel between agents working across JJ's machines.

This spec mirrors the implementation in `src/mail.py`. It is not a new design and not a list of changes. Distribution, packaging, the default DB path change, and any audit-driven trims belong in spec 002.

> **Completion rule:** This spec is complete when each acceptance criterion has been verified against `src/mail.py` via automated tests. If reality and spec disagree, the spec changes — the script is the source of truth.

## Goals

- Capture every command, flag, validation rule, and output shape in `mail.py` so the implementation can be moved into this repo without ambiguity.
- Establish parity acceptance criteria that future changes to the script's behavior must continue to satisfy unless the spec is updated first.
- Provide the behavioral baseline that spec 002's distribution work will package and dogfood.

## Requirements

### Functional Requirements

- **FR1**: Self-describe via `describe`, returning a single structured schema document covering tool purpose, identity rules, storage behavior, content-routing guidance, command schemas, and invariants. Invocation with no command produces the same output.
- **FR2**: Send ephemeral messages between agent identities, including direct messages, broadcasts, and replies, with per-message TTL.
- **FR3**: Read an agent's inbox, defaulting to unread messages, excluding the agent's own outgoing messages, and marking returned messages as read by default.
- **FR4**: Acknowledge a specific message as acted upon. Acknowledgement is a distinct state from read.
- **FR5**: Report per-agent `unread` and `unacked` counts derived from observed message traffic. No registration is required.
- **FR6**: Purge expired messages either explicitly via `cleanup` or opportunistically at the start of `send`, `read`, and `status`.
- **FR7**: Allow per-invocation database overrides via the `--db` flag and session-level overrides via the `AGENT_MAIL_DB` environment variable.
- **FR8**: Default all output to JSON on stdout and provide a top-level `--human` flag that switches every command to a human-readable rendering.

### Non-Functional Requirements

- **NFR1**: All success output is valid JSON on stdout when `--human` is absent, pretty-printed with two-space indentation and UTF-8 preserved (`ensure_ascii=False`).
- **NFR2**: All errors are emitted as JSON on stderr with the shape `{"error": "<message>"}` and produce a non-zero exit code.
- **NFR3**: `describe` runs without network access and without requiring an existing database file.
- **NFR4**: All commands except `describe` create the database file and parent directory on first use.

### Technical Constraints

- **TC1**: Agent identity grammar is `^[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*$`. Both halves are non-empty, lowercase alphanumeric plus hyphen, separated by a single colon.
- **TC2**: Identity validation runs everywhere an identity is read as input. The string `*` is permitted only as the value of `--to`; it is rejected anywhere else an identity is read.
- **TC3**: Text inputs (`--subject`, `--body`) reject any character with `ord(c) < 0x20` other than `\n`, `\r`, `\t`.
- **TC4**: `--refs` must parse as a JSON array of strings; the stored value is the canonical JSON re-serialization of that array.
- **TC5**: Default database path is `mail.db` next to the script. `AGENT_MAIL_DB` overrides the default. `--db <path>` overrides both for the current invocation by setting `AGENT_MAIL_DB` in-process.
- **TC6**: SQLite is the storage layer with `journal_mode = WAL`. Schema:
  - `messages(id PRIMARY KEY, sender, recipient, subject, body, refs, reply_to, type, ttl_hours, created, read_at, acked_at)` with indexes on `recipient`, `sender`, and `created`.
  - `broadcast_acks(message_id, agent, read_at, acked_at, PRIMARY KEY (message_id, agent))`.
- **TC7**: Message identifiers are UUID4 strings.
- **TC8**: Timestamps are ISO 8601 with timezone offset, produced by `datetime.now().astimezone().isoformat()`.
- **TC9**: Default TTL is 24 hours. A message is expired when `now > created + ttl_hours`.

## Key Decisions

These are decisions that span multiple requirements. They explain the script's shape without re-deriving it.

### `describe` is the schema, not help text

`describe` returns one structured document — purpose, identity rules, storage behavior, content-routing guidance, command schemas with arg types and examples, invariants. Agents consume the schema; they do not parse argparse `--help`. Every command, argument, output field, and rule must be discoverable from `describe` alone.

### Three-tier content routing

The schema's `content_routing` block tells the agent what belongs in a message versus a vault file versus a repo file. Messages are ephemeral coordination; durable knowledge lives in files referenced via `--refs`. This is documented rather than enforced because enforcement is impossible from a CLI — the agent has to make the call.

### No registration

Recipients do not need to exist before they are sent to or read for. An identity participates by reading its inbox. The `status` command derives the agent set from observed traffic. Onboarding is "pick a `project:name` and start."

### Broadcast as a distinct type, tracked per agent

A broadcast message exists once but is read and acked per recipient, so `broadcast_acks` is a separate table keyed by `(message_id, agent)`. Direct messages can carry their own `read_at` and `acked_at` columns because they have exactly one recipient.

### Self-exclusion in inbox queries

The reader's own messages are filtered out of their inbox in both default and `--all` modes. Without this rule, `read second-brain:main` would surface every message the agent itself sent.

### Read marks read; ack is a distinct, stronger state

Default `read` marks returned messages as read because that is the common case ("I am processing my inbox"). `--no-mark-read` is the opt-out. `ack` is a stronger statement than read — "I did something about this." `read_at` and `acked_at` are independent columns; nothing in the data couples them.

### Opportunistic cleanup

Expired messages are purged at the top of `send`, `read`, and `status` rather than only via the explicit `cleanup` command. This keeps the inbox accurate for any agent that calls those commands without requiring a daemon or scheduled job.

### `--human` exists alongside JSON

Output is JSON-first because the consumers are agents. `--human` exists for the moments JJ inspects the inbox directly. Both modes share the same data; `--human` only changes formatting.

## Command Contracts

### Identity Format

```text
project:name
```

- Lowercase alphanumeric plus hyphen.
- Exactly one colon separator.
- Project identifies the repo or work area; name identifies the session or role.

Examples: `second-brain:main`, `claudefana:deploy`, `agent-mail:reviewer`.

### Top-Level Flags

| Flag | Purpose |
|---|---|
| `--db <path>` | Override the database path for this invocation. Sets `AGENT_MAIL_DB` in-process. |
| `--human` | Switch all output from JSON to human-readable text. |

### `describe`

| Argument | Required | Purpose |
|---|---|---|
| `command` (positional) | no | Return the schema for a single command only |

Output:

| Variant | Output |
|---|---|
| `describe` | Full schema document with `name`, `description`, `usage`, `storage`, `agent_identity`, `content_routing`, `invariants`, and `commands` |
| `describe <command>` | `{ "<command>": <command_schema> }` |

### `send`

| Argument | Required | Default | Purpose |
|---|---|---|---|
| `--from` | yes | — | Sender identity |
| `--to` | yes | — | Recipient identity, or `"*"` for broadcast |
| `--subject` | yes | — | Subject line |
| `--body` | no | `""` | Message body |
| `--refs` | no | — | JSON array of file path references |
| `--reply-to` | no | — | Message id to reply to (creates a thread) |
| `--ttl` | no | `24` | Time-to-live in hours |

Output:

```json
{
  "id": "<uuid4>",
  "sender": "<id>",
  "recipient": "<id>|*",
  "subject": "<text>",
  "type": "direct|broadcast",
  "created": "<iso8601>",
  "ttl_hours": 24
}
```

### `read`

| Argument | Required | Default | Purpose |
|---|---|---|---|
| `agent` (positional) | yes | — | Recipient identity to read for |
| `--all` | no | `false` | Include already-read messages |
| `--from` | no | — | Filter by sender identity |
| `--limit` | no | `20` | Maximum messages returned |
| `--thread` | no | — | Return the entire thread for a message id |
| `--no-mark-read` | no | `false` | Return messages without marking them read |

Output is an array of message objects:

```json
[
  {
    "id": "<uuid4>",
    "sender": "<id>",
    "recipient": "<id>|*",
    "subject": "<text>",
    "body": "<text>",
    "refs": "<json-string-or-null>",
    "reply_to": "<uuid4-or-null>",
    "type": "direct|broadcast",
    "ttl_hours": 24,
    "created": "<iso8601>",
    "read_at": "<iso8601-or-null>",
    "acked_at": "<iso8601-or-null>"
  }
]
```

`refs` is returned as the JSON-encoded string stored in SQLite, not as a parsed array. This is a known wart that spec 002 may revisit.

Read semantics:

- Default mode returns unread direct messages addressed to `agent` plus unread broadcasts (where the broadcast has no `broadcast_acks` row with `read_at IS NOT NULL` for `agent`). Sender = `agent` is excluded.
- `--all` includes already-read messages, still excluding self-sent.
- `--from <sender>` adds a sender filter.
- `--limit <n>` caps the result, ordered by `created ASC`.
- `--thread <id>` walks `reply_to` up to the root, then expands the full thread via recursive CTE. Threads are returned in `created ASC` order and do not mark anything read.
- Default mode marks returned messages read: direct → update `messages.read_at`; broadcast → upsert `broadcast_acks(message_id, agent, read_at)`.

### `ack`

| Argument | Required | Purpose |
|---|---|---|
| `agent` (positional) | yes | Recipient identity acknowledging |
| `message_id` (positional) | yes | Message to mark acted upon |

Output:

```json
{ "message_id": "<uuid4>", "agent": "<id>", "acked_at": "<iso8601>" }
```

Direct messages set `messages.acked_at`. Broadcasts upsert `broadcast_acks(message_id, agent, acked_at)` so each agent's ack is independent.

### `status`

| Argument | Required | Purpose |
|---|---|---|
| `--agent` | no | Filter to a single identity |
| `--project` | no | Filter to all identities under a project prefix |

Output:

```json
[ { "agent": "<id>", "unread": 0, "unacked": 0 } ]
```

The agent set is derived from `senders ∪ recipients` (excluding `*`). Counts combine direct and broadcast messages, and exclude messages the agent itself sent.

### `cleanup`

| Argument | Required | Default | Purpose |
|---|---|---|---|
| `--dry-run` | no | `false` | Report expired messages without deleting |

Output:

| Case | Output |
|---|---|
| Nothing expired | `{ "deleted_count": 0 }` |
| Dry-run | `{ "dry_run": true, "would_delete": <n>, "oldest": "<iso>", "newest": "<iso>", "messages": [{ "id", "sender", "subject" }, …] }` |
| Real run | `{ "deleted_count": <n>, "oldest_deleted": "<iso>", "newest_deleted": "<iso>" }` |

`cleanup` deletes `broadcast_acks` rows first, then the messages.

## Acceptance Criteria

### Schema introspection

- [ ] **AC1**: `mail.py describe` prints valid JSON on stdout containing `name`, `description`, `usage`, `storage`, `agent_identity`, `content_routing`, `invariants`, and `commands` keys.
- [ ] **AC2**: `mail.py` with no arguments prints exactly the same JSON as `mail.py describe`.
- [ ] **AC3**: `mail.py describe send` prints `{ "send": { … } }` with the schema for `send` only; the same pattern works for every other command.
- [ ] **AC4**: `describe` produces identical output regardless of whether the database file exists.

### `send`

- [ ] **AC5**: `send --from <id> --to <id> --subject "<s>"` creates a message with `type = "direct"` and the documented output shape.
- [ ] **AC6**: `send --to "*"` produces `type = "broadcast"`.
- [ ] **AC7**: `send --refs '["a","b"]'` stores the array; subsequent `read` returns `refs` as the JSON string `["a","b"]`.
- [ ] **AC8**: `send --reply-to <id>` populates the `reply_to` column on the new message.
- [ ] **AC9**: `send --ttl <n>` overrides the default 24-hour TTL.

### `read`

- [ ] **AC10**: `read <agent>` returns unread direct messages addressed to `<agent>` plus unread broadcasts, excluding messages whose sender is `<agent>`.
- [ ] **AC11**: A second `read <agent>` after the first returns no messages by default (mark-read is the default for both direct and broadcast).
- [ ] **AC12**: `read <agent> --no-mark-read` returns messages without marking them read; subsequent `read <agent>` still returns them.
- [ ] **AC13**: `read <agent> --all` includes messages already marked read.
- [ ] **AC14**: `read <agent> --from <sender>` filters to messages from `<sender>` only.
- [ ] **AC15**: `read <agent> --limit <n>` caps the result count.
- [ ] **AC16**: `read <agent> --thread <id>` returns root + descendants in `created ASC` order and does not mutate `read_at` or `broadcast_acks`.
- [ ] **AC17**: For broadcasts, default `read` upserts `broadcast_acks` with `read_at` set; for direct messages it updates `messages.read_at` only.

### `ack`

- [ ] **AC18**: `ack <agent> <message-id>` for a direct message sets `messages.acked_at`.
- [ ] **AC19**: `ack <agent> <message-id>` for a broadcast upserts `broadcast_acks` with `acked_at` set, scoped to that agent only.
- [ ] **AC20**: `ack` against an unknown message id returns a JSON error on stderr with non-zero exit.

### `status`

- [ ] **AC21**: `status` returns one record per discovered agent (sender ∪ non-broadcast recipient), with combined `unread` and `unacked` counts across direct and broadcast messages, and excludes messages the agent itself sent.
- [ ] **AC22**: `status --agent <id>` filters to a single identity.
- [ ] **AC23**: `status --project <project>` filters to all identities whose project prefix matches `<project>:`.

### `cleanup`

- [ ] **AC24**: `cleanup --dry-run` returns the dry-run shape and does not delete any rows.
- [ ] **AC25**: `cleanup` deletes only messages where `now > created + ttl_hours` and removes their `broadcast_acks` rows first.
- [ ] **AC26**: `cleanup` with nothing expired returns `{ "deleted_count": 0 }`.

### Top-level flags

- [ ] **AC27**: `--db <path>` directs all reads and writes for the invocation to `<path>`; the default path is untouched.
- [ ] **AC28**: `AGENT_MAIL_DB` directs all reads and writes when `--db` is not provided.
- [ ] **AC29**: `--human` produces non-JSON, line-oriented output for every command. JSON mode remains the default.

### Validation

- [ ] **AC30**: An agent identity that does not match the grammar in TC1 produces a JSON error on stderr with non-zero exit. `*` is accepted only as a `--to` value.
- [ ] **AC31**: A `--subject` or `--body` containing a control character other than `\n`, `\r`, `\t` produces a JSON error on stderr with non-zero exit.
- [ ] **AC32**: A `--refs` value that does not parse as a JSON array of strings produces a JSON error on stderr with non-zero exit.

### Invariants and storage

- [ ] **AC33**: All success output is valid JSON on stdout when `--human` is absent.
- [ ] **AC34**: All errors are valid JSON on stderr with an `error` key and a non-zero exit code.
- [ ] **AC35**: Opportunistic cleanup runs at the start of `send`, `read`, and `status` (verified by inserting an already-expired message via direct DB write and observing it is purged on the next call).
- [ ] **AC36**: First-use database initialization creates both tables and indexes and enables WAL mode.
- [ ] **AC37**: Generated message ids are valid UUID4 strings; timestamps are ISO 8601 with timezone offset.

## Testing Approach

- Run automated tests against `src/mail.py` using a temporary `AGENT_MAIL_DB` per test so the default-path tests do not contaminate any real `mail.db` on the developer's machine.
- For each AC, record the exact command, environment, stdin, stdout JSON, stderr, and exit code as the parity baseline.
- The test fixtures produced here are the parity suite that spec 002 will reuse to assert the packaged binary behaves identically to the source script.

## Out of Scope

- Distribution, packaging, npx, pipx, ccburn pattern, GitHub Releases, npm wrappers — spec 002.
- Any change to the default database path — spec 002.
- Any addition, removal, or rename of a flag or command — handled by the audit between specs 001 and 002.
- MCP server, daemon, web UI, TUI, cross-machine sync, file locking, work queues, A2A compatibility.

## References

- Source script: [`src/mail.py`](../src/mail.py) — the implementation this spec describes.
- Strategic command center: `💼 Agent Mailbox.md` in JJ's second-brain vault.
- Project context: [PROJECT_UNDERSTANDING.md](../PROJECT_UNDERSTANDING.md).
