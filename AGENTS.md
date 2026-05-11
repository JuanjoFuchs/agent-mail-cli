# AGENTS.md

Agent Mail CLI is the open-source extraction of a working agent-to-agent inbox. `src/agent_mail/cli.py` is the source of truth for behavior. Spec 001 is the behavioral contract; spec 002 covers Python packaging, GitHub Releases binaries, and WinGet; spec 003 covers npm and `npx`.

**CRITICAL: You MUST read the required files BEFORE taking action.** This is not optional.

## Required Reading by Task

| User asks about... | READ THIS FIRST | Then act |
|---|---|---|
| Understanding the project | @PROJECT_UNDERSTANDING.md | Explain or explore |
| What the tool does today | @specs/001-agent-mail-cli.md, @src/agent_mail/cli.py | Answer using both |
| Modifying behavior | @specs/001-agent-mail-cli.md | Update spec first, then patch `src/agent_mail/cli.py` |
| Adding or changing a flag | @specs/001-agent-mail-cli.md | Spec, then code, then ACs |
| Auditing the surface (between specs 001 and 002) | @specs/001-agent-mail-cli.md, @src/agent_mail/cli.py | Propose trims; do not delete without explicit approval |
| PyPI / GitHub Releases / WinGet packaging | @specs/002-packaging.md | Implement per spec 002 |
| npm / `npx` distribution | @specs/003-npm-distribution.md | Implement per spec 003 (depends on spec 002) |
| Updating agent instructions | this file | Edit this index, keep it ~50 lines |

**Do not skip this step.** Read the linked file first, then act.

## Architecture

```text
src/agent_mail/cli.py  →  SQLite mailbox (default: ~/.agent-mail/mail.db; override AGENT_MAIL_DB)
```

Single Python script today. Spec is the contract; script is the implementation.

## Conventions

- JSON on stdout by default; JSON errors on stderr with `error` key; non-zero exit on error.
- `describe` is the canonical interface contract — every command, argument, and invariant must be discoverable from it alone.
- Identity: `project:name`, lowercase alphanumeric plus hyphen, single colon, both halves non-empty.
- Overrides: `AGENT_MAIL_DB` env var only. No top-level CLI flags in v1 — the audit removed `--db` and `--human`.
- Spec rules: `D:/jfuchs/dev/second-brain/Spec Writing Rules for Agents.md`. No "Future Considerations", no "Success Criteria"; every requirement traces to an AC.
- Commits: do not commit unless JJ explicitly asks.

## Workflow

1. **READ** — Routing table → required files → cross-references.
2. **SEARCH** — Inspect existing docs, specs, and the script.
3. **PLAN** — State the approach; flag scope creep.
4. **IMPLEMENT** — Spec change first when behavior changes; code follows.
5. **VERIFY** — Run the spec's ACs against the code before responding.

## Current State

- `src/agent_mail/cli.py` is the working Python source, packaged as `agent_mail`.
- Spec 001 is the behavioral contract for `src/agent_mail/cli.py`. Status: pending.
- Spec 001 audit complete (commit `be7a8c8`). `--ttl`, top-level `--db`, and `--human` removed; `--body-file`, `--fields`, and UUID validation added.
- Spec 002 (PyPI + GitHub Releases + WinGet, modeled on ccburn) has PyPI/GitHub Release verification complete; WinGet remains in Microsoft's review queue.
- Spec 003 (npm + `npx`, modeled on ccburn's npm wrapper) is in progress. npm publishes as `@juanjofuchs/agent-mail` because npm rejected unscoped `agent-mail`; the installed command remains `agent-mail`. npm Trusted Publishing is configured, and `v0.1.4` is the steady-state verification release.
- Strategic command center: `💼 Agent Mailbox.md` in JJ's private vault.
