# Landscape

Agent Mail CLI is not the first agent mailbox project. The positioning should be
honest: this project competes on low ceremony and runtime discoverability, not
category novelty.

## Nearby Projects

| Project | What It Is | Why Agent Mail CLI Is Different |
|---|---|---|
| MCP Agent Mail | Full MCP coordination layer with identities, inboxes, threads, search, and file leases | More capable, but requires MCP setup and a larger operating model |
| MACP | Multi-agent coordination protocol and local SQLite bus | Broader protocol/workspace layer; Agent Mail CLI is smaller and CLI-first |
| Gas Town | Multi-agent operating environment with orchestration and durable mail | Much heavier; Agent Mail CLI is a single coordination primitive |
| A2A | Cross-agent network protocol | Standards-track interoperability; not optimized for one local `npx` command |
| Agent Mailer | Async mailbox/protocol for coding agents | Close conceptually; Agent Mail CLI should differentiate on self-description and zero setup |

## Naming Search Notes

GitHub has multiple existing repositories named or related to `agent-mail`,
including exact `agent-mail` repos and the larger `mcp_agent_mail` project.

The npm package name `agent-mail` was checked on 2026-05-04 and appeared
available. `agent-mailbox` and `agent-inbox` were already taken.

## Positioning Sentence

Other systems give agents a coordination layer. Agent Mail CLI gives agents one
command that teaches them the coordination layer.
