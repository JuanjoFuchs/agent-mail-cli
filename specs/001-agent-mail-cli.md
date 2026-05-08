---
id: "001"
title: Agent Mail v1 — Behavioral Specification
status: pending
mirrors: src/agent_mail/cli.py
blocked_by: []
blocks: ["002"]
---

# Agent Mail v1 — Behavioral Specification

## Overview

This is the behavioral specification for Agent Mail (`src/agent_mail/cli.py`). It defines the v1 surface and behavior: `send`, `read`, `ack`, `status`, `cleanup`, `describe` — JSON in, JSON out, no daemon, no registration, no MCP.

The spec was first written as a retrospective mirror of the original script (built and used inside JJ's second-brain vault before this repo). It was then refined through an audit guided by Justin Poehnelt's *["You Need to Rewrite Your CLI for AI Agents"](https://justin.poehnelt.com/posts/rewrite-your-cli-for-ai-agents/)*. The trims and additions from that audit are recorded in **Key Decisions** and reflected in every other section.

Distribution, packaging, and the packaged default DB path change belong in spec 002.

> **Completion rule:** This spec is complete when each acceptance criterion has been verified against `src/agent_mail/cli.py` via automated tests. The package source is the source of truth — if reality and spec disagree, the spec is updated to match (or the package source is patched after a spec change). Behavior changes are spec-first.

## Goals

- Capture every command, flag, validation rule, and output shape in `src/agent_mail/cli.py` so the contract is unambiguous.
- Establish parity acceptance criteria that future changes to the script's behavior must continue to satisfy unless the spec is updated first.
- Provide the behavioral baseline that spec 002's distribution work will package and dogfood.

## Requirements

### Functional Requirements

- **FR1**: Self-describe via `describe`, returning a single structured schema document covering tool purpose, identity rules, storage behavior, content-routing guidance, command schemas, and invariants. `describe <command>` returns `{ "<command>": {…} }`. Invocation with no command produces the full-schema output.
- **FR2**: Send ephemeral messages between agent identities, including direct messages, broadcasts, and replies. All messages live for a fixed 24 hours. Body content is supplied either inline via `--body` or from a UTF-8 file via `--body-file`.
- **FR3**: Read an agent's inbox, defaulting to unread messages, excluding the agent's own outgoing messages, and marking returned messages as read by default. Output may be projected to a subset of fields via `--fields`.
- **FR4**: Acknowledge a specific message as acted upon. Acknowledgement is a distinct state from read. The message id input is validated as a UUID before any database lookup.
- **FR5**: Report per-agent `unread` and `unacked` counts derived from observed message traffic. No registration is required. Output may be projected to a subset of fields via `--fields`.
- **FR6**: Purge expired messages either explicitly via `cleanup` or opportunistically at the start of `send`, `read`, and `status`.
- **FR7**: Override the database path via the `AGENT_MAIL_DB` environment variable. There is no other override mechanism.

### Non-Functional Requirements

- **NFR1**: All success output is valid JSON on stdout, pretty-printed with two-space indentation and UTF-8 preserved (`ensure_ascii=False`).
- **NFR2**: All application errors are emitted as JSON on stderr with the shape `{"error": "<message>"}` and produce a non-zero exit code. Argparse-level errors (unrecognized argument, missing required flag) follow argparse's default behavior and are out of scope for the JSON-error contract.
- **NFR3**: `describe` runs without network access and without requiring an existing database file.
- **NFR4**: All commands except `describe` create the database file and parent directory on first use.

### Technical Constraints

- **TC1**: Agent identity grammar is `^[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*$`. Both halves are non-empty, lowercase alphanumeric plus hyphen, separated by a single colon.
- **TC2**: Identity validation runs everywhere an identity is read as input. The string `*` is permitted only as the value of `--to`; it is rejected anywhere else an identity is read.
- **TC3**: Text inputs (`--subject`, `--body`, and the contents read from `--body-file`) reject any character with `ord(c) < 0x20` other than `\n`, `\r`, `\t`.
- **TC4**: `--refs` must parse as a JSON array of strings; the stored value is the canonical JSON re-serialization of that array.
- **TC5**: UUID validation runs on every UUID-shaped input — `ack <message_id>`, `send --reply-to`, and `read --thread`. Format: `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$` (case-insensitive).
- **TC6**: `--body-file` reads UTF-8 text. Non-existent paths, paths that are not regular files, and non-UTF-8 contents produce a JSON error on stderr. `--body` and `--body-file` are mutually exclusive; passing both is an error.
- **TC7**: `--fields` parses as a comma-separated list; each entry must appear in the command's documented `output_fields`. Unknown entries produce a JSON error on stderr listing the invalid names and the valid set.
- **TC8**: Default database path is `~/.agent-mail/mail.db` in packaged/source-package execution. `AGENT_MAIL_DB` overrides the default. No other override mechanism exists in v1.
- **TC9**: SQLite is the storage layer with `journal_mode = WAL`. Schema:
  - `messages(id PRIMARY KEY, sender, recipient, subject, body, refs, reply_to, type, ttl_hours, created, read_at, acked_at)` with indexes on `recipient`, `sender`, and `created`.
  - `broadcast_acks(message_id, agent, read_at, acked_at, PRIMARY KEY (message_id, agent))`.
- **TC10**: Message identifiers are UUID4 strings.
- **TC11**: Timestamps are ISO 8601 with timezone offset, produced by `datetime.now().astimezone().isoformat()`.
- **TC12**: All messages have a fixed 24-hour TTL. Expiration: `now > created + 24h`. The `ttl_hours` column is retained at value 24 for forward compatibility with future per-message TTL.

## Key Decisions

These are decisions that span multiple requirements. They are split into the original design (carried over from the script as built) and the audit (trims and additions made under the Poehnelt article's guidance).

### Original design

#### `describe` is the schema, not help text

`describe` returns one structured document — purpose, identity rules, storage behavior, content-routing guidance, command schemas with arg types and examples, invariants. Agents consume the schema; they do not parse argparse `--help`. Every command, argument, output field, and rule must be discoverable from `describe` alone. The corollary: there is no separate `SKILL.md` or `CONTEXT.md` companion file. `describe` is canonical.

#### Three-tier content routing

The schema's `content_routing` block tells the agent what belongs in a message versus a vault file versus a repo file. Messages are ephemeral coordination; durable knowledge lives in files referenced via `--refs`. Documented rather than enforced because enforcement is impossible from a CLI.

#### No registration

Recipients do not need to exist before they are sent to or read for. An identity participates by reading its inbox. The `status` command derives the agent set from observed traffic.

#### Broadcast as a distinct type, tracked per agent

A broadcast message exists once but is read and acked per recipient, so `broadcast_acks` is a separate table keyed by `(message_id, agent)`. Direct messages can carry their own `read_at` and `acked_at` columns because they have exactly one recipient.

#### Self-exclusion in inbox queries

The reader's own messages are filtered out of their inbox in both default and `--all` modes. Without this rule, `read second-brain:main` would surface every message the agent itself sent.

#### Read marks read; ack is a distinct, stronger state

Default `read` marks returned messages as read. `--no-mark-read` is the opt-out. `ack` is a stronger statement — "I did something about this." `read_at` and `acked_at` are independent columns; nothing in the data couples them.

#### Opportunistic cleanup

Expired messages are purged at the top of `send`, `read`, and `status` rather than only via the explicit `cleanup` command. This keeps the inbox accurate without a daemon or scheduled job.

### Audit (post-Poehnelt review)

#### Single fixed TTL — no `--ttl` override

All messages live exactly 24 hours. The original implementation accepted `--ttl <n>` to override this, but the override was never used in practice. Removing it shrinks the `send` surface and the schema. The `ttl_hours` column stays in the messages table so a future spec can re-introduce per-message TTL without a migration.

#### Single DB override path — no `--db` flag

`AGENT_MAIL_DB` is the only override. The original `--db` top-level flag was a redundant alias that just set the env var in-process. Tests and ad-hoc invocations use `AGENT_MAIL_DB=path agent-mail …` (one-shot env on the same line works in any shell).

#### JSON-only output — no `--human` mode

The tool is agent-first. The original `--human` flag rendered a parallel line-oriented format for direct human inspection. With the tool's role narrowed to agent coordination, `--human` is dead weight; humans inspecting raw output can pipe through `python -m json.tool` or just read indented JSON. Removing it deletes a parallel formatting code path and one more flag the agent might be tempted to use.

#### `--body-file` solves shell escaping (added)

Multi-line bodies with code blocks, markdown, or special characters reliably break shell quoting (bash, PowerShell, both). Agents converge on a `cat tempfile | agent-mail send --body "$(cat tempfile)"` workaround anyway. `--body-file <path>` makes the temp-file path the supported path: write the file, pass the path, no escaping. Mutually exclusive with `--body`. Only `--body` gets this treatment because subjects and other inputs are line-length by design.

#### `--fields` for context window discipline (added)

Server-side projection on `read` and `status`. The agent specifies `--fields id,sender,subject` to receive only the fields it cares about for a given inbox scan. Aligns with Pattern 3 from the article ("APIs return massive blobs … always use field masks"). Validates against the command's documented `output_fields`; unknown names error early.

#### UUID validation on identifier inputs (added)

`ack <message_id>`, `send --reply-to`, and `read --thread` all validate the input as a UUID before reaching the database. Hallucinated formats fail fast with a clear error rather than producing a silent miss or "message not found." Aligns with Pattern 4 (input hardening).

#### CLI-only in v1 — no MCP server

MCP setup is the friction this tool removes. `agent-mail describe` (and later `npx -y agent-mail describe`) is the wedge: immediate JSON schema without MCP setup. Adding an MCP surface in v1 would put us in the same complexity tier as the systems we're differentiating against. Reconsider in a future spec if there is real demand from clients without easy shell-out.

#### No `--json` payload input

Pattern 1 in the article recommends `--json '{...}'` for nested API payloads. Agent Mail's message schema is flat (six user-controlled fields), so flat flags map cleanly. `--refs` already takes JSON for the one nested field. A parallel `--json` input would be redundant.

#### No `--dry-run` on `send` or `ack`

These operations are not destructive. `send` creates a row that auto-expires; `ack` flips a flag. Adding `--dry-run` would invite agents to consume an extra turn validating actions that have negligible cost to retry. `cleanup --dry-run` stays because cleanup is destructive.

#### No prompt-injection sanitization

Agent Mail's threat model is local agents in the same trust domain. Prompt injection in message bodies is a downstream concern handled by the harness (Claude Code, Codex, Cursor) the agent runs under. Adding a `--sanitize` template would duplicate work the harness already does.

#### No recipient verification on `ack`

`ack <agent> <message_id>` does not check that `<agent>` matches `messages.recipient`. The threat (one agent forging an ack on another's behalf) is low in a local trust domain, and the simplicity matches the rest of the no-registration design.

#### No path canonicalization on `--refs`

`--refs` stores caller-supplied paths verbatim. The CLI never opens those paths. Path traversal protection is the responsibility of whoever consumes the refs downstream, not the mailbox.

#### `refs` returned as JSON-encoded string

Stored and returned as a JSON string rather than a parsed array. A known wart preserved for now to keep storage and output symmetric. A future spec may parse on read.

## Command Contracts

### Identity Format

```text
project:name
```

- Lowercase alphanumeric plus hyphen.
- Exactly one colon separator.
- Both halves non-empty.
- Project identifies the repo or work area; name identifies the session or role.

Examples: `second-brain:main`, `claudefana:deploy`, `agent-mail:reviewer`.

### Top-Level Flags

There are no top-level flags in v1. The previous `--db` and `--human` flags were removed in the audit.

### `describe`

| Argument | Required | Purpose |
|---|---|---|
| `command` (positional) | no | Return the schema for a single command only |

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
| `--body` | no | — | Inline message body. Mutually exclusive with `--body-file`. |
| `--body-file` | no | — | Read message body from a UTF-8 file. Mutually exclusive with `--body`. |
| `--refs` | no | — | JSON array of file path references |
| `--reply-to` | no | — | Message UUID to reply to (creates a thread) |

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
| `--thread` | no | — | Return the entire thread for a message UUID |
| `--no-mark-read` | no | `false` | Return messages without marking them read |
| `--fields` | no | — | Comma-separated subset of `output_fields` to include in each result |

Output is an array of message objects (full shape; `--fields` projects to a subset):

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

`refs` is returned as the JSON-encoded string stored in SQLite, not as a parsed array (see Key Decisions).

Read semantics:

- Default mode returns unread direct messages addressed to `agent` plus unread broadcasts (where the broadcast has no `broadcast_acks` row with `read_at IS NOT NULL` for `agent`). Sender = `agent` is excluded.
- `--all` includes already-read messages, still excluding self-sent.
- `--from <sender>` adds a sender filter (validated as an identity).
- `--limit <n>` caps the result, ordered by `created ASC`.
- `--thread <uuid>` walks `reply_to` up to the root, then expands the full thread via recursive CTE. Threads are returned in `created ASC` order and do not mark anything read.
- Default mode marks returned messages read: direct → update `messages.read_at`; broadcast → upsert `broadcast_acks(message_id, agent, read_at)`. Mark-read happens before field projection so identifiers are still available for the upserts.

### `ack`

| Argument | Required | Purpose |
|---|---|---|
| `agent` (positional) | yes | Recipient identity acknowledging |
| `message_id` (positional) | yes | UUID of the message to mark acted upon |

Output:

```json
{ "message_id": "<uuid4>", "agent": "<id>", "acked_at": "<iso8601>" }
```

Direct messages set `messages.acked_at`. Broadcasts upsert `broadcast_acks(message_id, agent, acked_at)` so each agent's ack is independent. The acker does not need to be the addressed recipient (see Key Decisions).

### `status`

| Argument | Required | Default | Purpose |
|---|---|---|---|
| `--agent` | no | — | Filter to a single identity |
| `--project` | no | — | Filter to all identities under a project prefix |
| `--fields` | no | — | Comma-separated subset of `output_fields` to include in each result |

Output:

```json
[ { "agent": "<id>", "unread": 0, "unacked": 0 } ]
```

The agent set is derived from `senders ∪ recipients` (excluding `*`). Counts combine direct and broadcast messages, and exclude messages the agent itself sent.

### `cleanup`

| Argument | Required | Default | Purpose |
|---|---|---|---|
| `--dry-run` | no | `false` | Report expired messages without deleting |

| Case | Output |
|---|---|
| Nothing expired | `{ "deleted_count": 0 }` |
| Dry-run | `{ "dry_run": true, "would_delete": <n>, "oldest": "<iso>", "newest": "<iso>", "messages": [{ "id", "sender", "subject" }, …] }` |
| Real run | `{ "deleted_count": <n>, "oldest_deleted": "<iso>", "newest_deleted": "<iso>" }` |

`cleanup` deletes `broadcast_acks` rows first, then the messages.

## Acceptance Criteria

### Schema introspection

- [ ] **AC1**: `agent-mail describe` prints valid JSON on stdout containing `name`, `description`, `usage`, `storage`, `agent_identity`, `content_routing`, `invariants`, and `commands` keys.
- [ ] **AC2**: `agent-mail` with no arguments prints exactly the same JSON as `agent-mail describe`.
- [ ] **AC3**: `agent-mail describe send` prints `{ "send": { … } }` with the schema for `send` only; the same pattern works for every other command.
- [ ] **AC4**: `describe` produces identical output regardless of whether the database file exists.

### `send`

- [ ] **AC5**: `send --from <id> --to <id> --subject "<s>"` creates a message with `type = "direct"` and the documented output shape, including `ttl_hours: 24`.
- [ ] **AC6**: `send --to "*"` produces `type = "broadcast"`.
- [ ] **AC7**: `send --refs '["a","b"]'` stores the array; subsequent `read` returns `refs` as the JSON string `["a","b"]`.
- [ ] **AC8**: `send --reply-to <uuid>` populates the `reply_to` column on the new message.
- [ ] **AC9**: `send --reply-to not-a-uuid` returns a JSON error on stderr with non-zero exit; no row is inserted.
- [ ] **AC10**: `send --body-file <path>` reads `<path>` as UTF-8 and stores its contents as the body; the round-tripped body equals the file's bytes.
- [ ] **AC11**: `send --body x --body-file <path>` returns a JSON error on stderr with non-zero exit.
- [ ] **AC12**: `send --body-file /no/such/path` returns a JSON error on stderr with non-zero exit.
- [ ] **AC13**: `send --body-file <non-utf8-file>` returns a JSON error on stderr with non-zero exit.

### `read`

- [ ] **AC14**: `read <agent>` returns unread direct messages addressed to `<agent>` plus unread broadcasts, excluding messages whose sender is `<agent>`.
- [ ] **AC15**: A second `read <agent>` after the first returns no messages by default (mark-read is the default for both direct and broadcast).
- [ ] **AC16**: `read <agent> --no-mark-read` returns messages without marking them read; subsequent `read <agent>` still returns them.
- [ ] **AC17**: `read <agent> --all` includes messages already marked read.
- [ ] **AC18**: `read <agent> --from <sender>` filters to messages from `<sender>` only.
- [ ] **AC19**: `read <agent> --limit <n>` caps the result count.
- [ ] **AC20**: `read <agent> --thread <uuid>` returns root + descendants in `created ASC` order and does not mutate `read_at` or `broadcast_acks`.
- [ ] **AC21**: `read <agent> --thread not-a-uuid` returns a JSON error on stderr with non-zero exit.
- [ ] **AC22**: For broadcasts, default `read` upserts `broadcast_acks` with `read_at` set; for direct messages it updates `messages.read_at` only.
- [ ] **AC23**: `read <agent> --fields id,sender,subject` returns objects containing only those keys, in the same order as the input list.
- [ ] **AC24**: `read <agent> --fields nope` returns a JSON error on stderr listing the invalid name(s) and the valid `output_fields` set.

### `ack`

- [ ] **AC25**: `ack <agent> <uuid>` for a direct message sets `messages.acked_at`.
- [ ] **AC26**: `ack <agent> <uuid>` for a broadcast upserts `broadcast_acks` with `acked_at` set, scoped to that agent only.
- [ ] **AC27**: `ack <agent> not-a-uuid` returns a JSON error on stderr with non-zero exit; no rows are touched.
- [ ] **AC28**: `ack <agent> <unknown-uuid>` returns a JSON error on stderr with non-zero exit.

### `status`

- [ ] **AC29**: `status` returns one record per discovered agent (sender ∪ non-broadcast recipient), with combined `unread` and `unacked` counts across direct and broadcast messages, and excludes messages the agent itself sent.
- [ ] **AC30**: `status --agent <id>` filters to a single identity.
- [ ] **AC31**: `status --project <project>` filters to all identities whose project prefix matches `<project>:`.
- [ ] **AC32**: `status --fields agent,unread` returns objects containing only those keys.
- [ ] **AC33**: `status --fields nope` returns a JSON error on stderr.

### `cleanup`

- [ ] **AC34**: `cleanup --dry-run` returns the dry-run shape and does not delete any rows.
- [ ] **AC35**: `cleanup` deletes only messages where `now > created + 24h` and removes their `broadcast_acks` rows first.
- [ ] **AC36**: `cleanup` with nothing expired returns `{ "deleted_count": 0 }`.

### Storage and overrides

- [ ] **AC37**: `AGENT_MAIL_DB=<path> agent-mail …` directs all reads and writes to `<path>`; the default path is untouched.
- [ ] **AC38**: First-use database initialization creates both tables and indexes and enables WAL mode.

### Validation

- [ ] **AC39**: An agent identity that does not match the grammar in TC1 produces a JSON error on stderr with non-zero exit. `*` is accepted only as a `--to` value.
- [ ] **AC40**: A `--subject`, `--body`, or `--body-file` content containing a control character other than `\n`, `\r`, `\t` produces a JSON error on stderr with non-zero exit.
- [ ] **AC41**: A `--refs` value that does not parse as a JSON array of strings produces a JSON error on stderr with non-zero exit.

### Invariants

- [ ] **AC42**: All success output is valid JSON on stdout.
- [ ] **AC43**: All application errors are valid JSON on stderr with an `error` key and a non-zero exit code.
- [ ] **AC44**: Opportunistic cleanup runs at the start of `send`, `read`, and `status` (verified by inserting an already-expired message via direct DB write and observing it is purged on the next call).
- [ ] **AC45**: Generated message ids are valid UUID4 strings; timestamps are ISO 8601 with timezone offset.
- [ ] **AC46**: Every send records `ttl_hours = 24` in the messages table.

## Testing Approach

- Run automated tests against `src/agent_mail/cli.py` using a temporary `AGENT_MAIL_DB` per test so default-path tests do not contaminate any real mailbox on the developer's machine.
- For each AC, record the exact command, environment, stdin, stdout JSON, stderr, and exit code as the parity baseline.
- The test fixtures produced here are the parity suite that spec 002 will reuse to assert the packaged binary behaves identically to the source script.

## Out of Scope

- Distribution, packaging, npx, pipx, ccburn pattern, GitHub Releases, npm wrappers — spec 002.
- Default DB path change for the packaged binary — spec 002.
- `--json` payload input — flat schema, see Key Decisions.
- MCP server, daemon, web UI, TUI — see Key Decisions.
- `SKILL.md` or other companion documentation files — `describe` is canonical.
- `--dry-run` on `send` or `ack` — non-destructive operations.
- Prompt-injection sanitization — harness responsibility.
- Recipient verification on `ack` — local trust domain.
- Path canonicalization on `--refs` — caller's responsibility.
- Cross-machine sync, file locking, work queues, A2A compatibility.

## References

- Source package: [`src/agent_mail/cli.py`](../src/agent_mail/cli.py) — the implementation this spec describes.
- Audit guidance: Justin Poehnelt, *["You Need to Rewrite Your CLI for AI Agents"](https://justin.poehnelt.com/posts/rewrite-your-cli-for-ai-agents/)*. The patterns informed every entry under Key Decisions § Audit.
- Strategic command center: `💼 Agent Mailbox.md` in JJ's second-brain vault.
- Project context: [PROJECT_UNDERSTANDING.md](../PROJECT_UNDERSTANDING.md).
