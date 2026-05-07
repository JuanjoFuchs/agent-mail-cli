# Project Understanding

## Summary

Agent Mail CLI is a self-describing local inbox for coding agents. Its core promise: an agent can run one command, learn the tool from structured JSON, and coordinate with other agents without MCP setup, a daemon, or a prior install.

```bash
npx -y agent-mail describe
```

The tool already exists and works. It was built and used as `mail.py` inside JJ's private second-brain vault before this repo. This repo is the open-source extraction of that tool: the Python source is ported as-is into `src/mail.py`, spec 001 is the behavioral mirror of that script, and spec 002 (pending) will cover distribution (pip, npx) so users can install and run the tool without cloning this repo.

## Problem

Multi-agent coding workflows need a small coordination channel for handoffs, status, requests, acknowledgements, and replies. Existing solutions prove the need but solve a larger problem: most start by asking the user to install an MCP server, initialize a workspace, run a daemon, adopt an orchestration framework, or reason about a network protocol.

The first 30 seconds of use is the gap:

> I am already inside Claude Code or Codex. I need this agent to send a handoff to that agent. I want one command that teaches both sides the mailbox.

## Product Decision

Agent Mail CLI competes on **low ceremony and runtime discoverability**, not category novelty.

| Decision | Choice |
|---|---|
| Product name | Agent Mail CLI |
| Repository | `agent-mail-cli` |
| Source of truth for behavior | `src/mail.py` (Python) |
| First command | `agent-mail describe` |
| First distribution paths (spec 002) | `npx -y agent-mail` and `pipx run agent-mail` |
| Persistence | SQLite |
| Default DB path (today) | `mail.db` next to the script |
| Default DB path (spec 002 will revisit) | TBD — likely `~/.agent-mail/mail.db` for the packaged binary |
| Override env var | `AGENT_MAIL_DB` |
| Per-invocation override | `--db <path>` |

## Target Users

The first users are developers already running coding agents (Claude Code, Codex, Cursor, OpenCode, similar). They generally have Node and npm installed because the agent ecosystem commonly depends on Node tooling. Most also have Python because the script's first audience is Python-leaning. Spec 002 must keep the install path frictionless for both — npx for Node-leaning users, pipx for Python-leaning users.

## Target Interaction

Sender:

```text
Run `npx -y agent-mail describe`. Your identity is `second-brain:main`.
Send a message to `ccburn:worker` with this context.
```

Receiver:

```text
Run `npx -y agent-mail describe`. Your identity is `ccburn:worker`.
Check your inbox and act on any unread messages.
```

The human writes one or two sentences. `describe` does the rest.

## Core Concepts

### Runtime schema is the interface

`describe` is the canonical interface contract for agents — not a help-text afterthought. It must explain tool purpose, identity rules, storage behavior, content-routing guidance, command schemas, examples, and safety invariants in structured JSON.

### Messages are ephemeral

The mailbox is for coordination, not knowledge. If information should outlive the current unit of work, it belongs in a file and the message references that file via `--refs`.

### No registration

Recipients do not need to exist before receiving messages. An identity participates by reading its inbox.

### Local durable state

Mailbox state lives outside the npm cache or temporary package paths so messages persist across repeated `npx` invocations and across projects.

### Boring persistence

SQLite is the storage layer because unread state, ack state, TTL cleanup, reply threads, and concurrent local writes all become awkward with a flat JSON file. Spec 002 will keep SQLite and ensure the bundled binary ships with it embedded.

## Competitive Frame

Agent Mail CLI is the smallest useful point on the complexity curve.

| Alternative | Better When | Agent Mail CLI Difference |
|---|---|---|
| MCP Agent Mail | You want a full MCP coordination layer | Agent Mail CLI starts with one `npx`/`pipx` command |
| MACP | You want a broader coordination protocol/workspace | Agent Mail CLI is CLI-first and narrower |
| Gas Town | You want a multi-agent operating environment | Agent Mail CLI is only the mailbox primitive |
| A2A | You need cross-network agent interoperability | Agent Mail CLI is local-first |
| Ad hoc files | You need a one-off scratchpad | Agent Mail CLI adds read/ack/status/TTL semantics |

Positioning sentence: *Other systems give agents a coordination layer. Agent Mail CLI gives agents one command that teaches them the coordination layer.*

## Plan

The repo work proceeds in deliberate steps:

1. **Spec 001 — behavioral mirror.** Document exactly what `src/mail.py` does today (no additions, no removals).
2. **Copy the script.** Port `mail.py` into `src/mail.py` byte-for-byte.
3. **Audit.** Review the script's surface (flags, behaviors, output shapes) against actual usage. Trim fluff with JJ's discretion. Both spec 001 and `src/mail.py` are revised together.
4. **Spec 002 — distribution.** Package the audited script for pip and npx using the ccburn pattern. Define the default DB path change for the packaged binary, the migration story for the legacy path, and the parity acceptance criteria.
5. **Implement spec 002.** Build, ship, dogfood. Replace JJ's daily use of `python scripts/mail.py` with the packaged version.
6. **Delete the upstream.** Once JJ is satisfied with the packaged tool, the original `scripts/mail.py` in the second-brain vault is removed; this repo becomes the only home.

## Scope

The active behavioral scope is described in [`specs/001-agent-mail-cli.md`](specs/001-agent-mail-cli.md).

**Included:**

- Self-describing `describe`
- `send`, `read`, `ack`, `status`, `cleanup`
- Local SQLite mailbox
- `AGENT_MAIL_DB` override and top-level `--db` flag
- `--human` output mode

**Excluded (not in v1):**

- MCP server
- Daemon
- Web UI or TUI
- Cross-machine sync
- A2A compatibility
- File locks or work queues

## Repository State

| File | Purpose |
|---|---|
| `AGENTS.md` | Compressed routing index for agents |
| `CLAUDE.md` | Claude Code pointer to `AGENTS.md` |
| `PROJECT_UNDERSTANDING.md` | Durable project context and decisions (this file) |
| `README.md` | Human-facing project overview |
| `CHANGELOG.md` | Release notes |
| `LICENSE` | MIT license |
| `docs/landscape.md` | Competitive and naming research |
| `specs/001-agent-mail-cli.md` | Behavioral specification of `src/mail.py` |
| `src/mail.py` | Python implementation, ported from JJ's private vault |

No packaging, npm wrapper, CI, or release workflow exists yet — that lands in spec 002.

## Origin

Agent Mail CLI is the open-source extraction of `mail.py`, a Python CLI JJ built and used inside his second-brain vault. That script proved the design (SQLite, `project:name` identity, pull-based delivery, three-tier content routing, `describe` as the interface). This repo's job is to distribute it.

The strategic command center for this project lives at `💼 Agent Mailbox.md` in JJ's private second-brain vault. That note holds the broader research on inter-agent communication (Gas Town's two-channel model, A2A protocol, MCP Agent Mail, Overstory, Meshpocalypse, FIPA ACL history) and the strategic frame for the public extraction.
