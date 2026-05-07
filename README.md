# Agent Mail CLI

A self-describing local inbox for coding agents.

```bash
npx -y agent-mail describe
```

That command is the product wedge: an agent can run it, read the JSON schema,
and learn how to send, read, acknowledge, and inspect messages without MCP
setup, a daemon, or separate documentation.

## Status

This repository is the open-source extraction of a working internal tool.
`src/mail.py` is the Python implementation, ported as-is from a private
vault, and is the source of truth for behavior. Spec 001 is the behavioral
specification of that script. Spec 002, pending, will cover distribution
(pip, npx) so the tool can be installed and run without cloning this repo.

## Why

Multi-agent coding workflows need coordination. Heavy systems already exist
for that: MCP servers, agent frameworks, workspace managers, and network
protocols.

Agent Mail CLI is aimed at the simpler moment:

> I am already inside Claude Code or Codex. I need this agent to send a
> handoff to that agent. I want one command that teaches both sides the
> mailbox.

## Intended Usage

Once distribution lands (spec 002), the target experience is one command:

Sender:

```bash
npx -y agent-mail describe
npx -y agent-mail send --from second-brain:main --to ccburn:worker --subject "Review spec" --body "Please read the referenced spec and report risks."
```

Recipient:

```bash
npx -y agent-mail describe
npx -y agent-mail read ccburn:worker
```

Until then, the script can be run directly:

```bash
python src/mail.py describe
```

## Design Goals

- Runtime schema introspection through `describe`
- JSON output by default
- JSON errors on stderr
- Local durable mailbox state
- No registration
- No daemon
- No MCP server required for v1
- Stable storage outside npm cache (post-packaging)
- One-command install for users without the source script

## Repository Structure

```text
.
├── AGENTS.md
├── CHANGELOG.md
├── CLAUDE.md
├── LICENSE
├── PROJECT_UNDERSTANDING.md
├── README.md
├── docs/
│   └── landscape.md
├── specs/
│   └── 001-agent-mail-cli.md
└── src/
    └── mail.py
```

## Specs

- [specs/001-agent-mail-cli.md](specs/001-agent-mail-cli.md) — behavioral
  specification of `src/mail.py`. Status: pending review.
- Spec 002 (distribution) is not yet written.

## Naming

- Product: Agent Mail CLI
- Repo: `agent-mail-cli`
- Target npm package / command: `agent-mail`
- Target Python package: TBD in spec 002

## License

MIT
