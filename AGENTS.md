# AGENTS.md

Agent Mail CLI is the open-source extraction of a working agent-to-agent inbox. `src/mail.py` (ported from a private internal tool) is the source of truth for behavior. Spec 001 is the behavioral mirror; spec 002 (pending) will cover packaging and distribution.

**CRITICAL: You MUST read the required files BEFORE taking action.** This is not optional.

## Required Reading by Task

| User asks about... | READ THIS FIRST | Then act |
|---|---|---|
| Understanding the project | @PROJECT_UNDERSTANDING.md | Explain or explore |
| What the tool does today | @specs/001-agent-mail-cli.md, @src/mail.py | Answer using both |
| Modifying behavior | @specs/001-agent-mail-cli.md | Update spec first, then patch `src/mail.py` |
| Adding or changing a flag | @specs/001-agent-mail-cli.md | Spec, then code, then ACs |
| Auditing the surface (between specs 001 and 002) | @specs/001-agent-mail-cli.md, @src/mail.py | Propose trims; do not delete without explicit approval |
| Packaging or distribution | @PROJECT_UNDERSTANDING.md | Wait — spec 002 is not yet written |
| Updating agent instructions | this file | Edit this index, keep it ~50 lines |

**Do not skip this step.** Read the linked file first, then act.

## Architecture

```text
src/mail.py  →  SQLite mailbox (default: mail.db next to script; override AGENT_MAIL_DB)
```

Single Python script today. Spec is the contract; script is the implementation.

## Conventions

- JSON on stdout by default; JSON errors on stderr with `error` key; non-zero exit on error.
- `describe` is the canonical interface contract — every command, argument, and invariant must be discoverable from it alone.
- Identity: `project:name`, lowercase alphanumeric plus hyphen, single colon, both halves non-empty.
- Overrides: only `AGENT_MAIL_DB` env var and top-level `--db` flag.
- Spec rules: `D:/jfuchs/dev/second-brain/Spec Writing Rules for Agents.md`. No "Future Considerations", no "Success Criteria"; every requirement traces to an AC.
- Commits: do not commit unless JJ explicitly asks.

## Workflow

1. **READ** — Routing table → required files → cross-references.
2. **SEARCH** — Inspect existing docs, specs, and the script.
3. **PLAN** — State the approach; flag scope creep.
4. **IMPLEMENT** — Spec change first when behavior changes; code follows.
5. **VERIFY** — Run the spec's ACs against the code before responding.

## Current State

- `src/mail.py` is the working Python source, ported as-is from JJ's vault.
- Spec 001 is a behavioral mirror of `src/mail.py`. Status: pending.
- Spec 002 (pip + npx distribution) is the next planned spec. Not yet written.
- An audit step is planned between specs 001 and 002 to trim surface fluff with JJ's discretion.
- Strategic command center: `💼 Agent Mailbox.md` in JJ's private vault.
