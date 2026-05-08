---
id: "002"
title: Agent Mail Packaging
status: in_progress
blocked_by: ["001"]
blocks: ["003"]
---

# Agent Mail Packaging

## Overview

Package the audited Agent Mail CLI behavior from spec 001 as a Python distribution on PyPI, platform binaries on GitHub Releases, and a WinGet package for Windows users. npm distribution is intentionally separate and is covered by spec 003.

The PyPI distribution name is `agent-mail-cli` because PyPI rejected `agent-mail` as too similar to an existing project. The installed command remains `agent-mail`, preserving the product wedge and the future `npx -y agent-mail describe` path.

> **Completion rule:** This spec is not complete until all acceptance criteria are verified through the testing approach below, including real installs from real publish channels: `pipx install agent-mail-cli` on a clean machine and `winget install JuanjoFuchs.agent-mail-cli` on a clean Windows machine after Microsoft approval. Build-only and CI-only verification are insufficient. The agent must iterate until verification passes.

## Goals

- Make `agent-mail` runnable on a fresh machine through Python packaging (`pip`, `pipx`) and WinGet.
- Preserve the complete spec 001 command behavior when invoked through installed packages and release binaries.
- Publish reproducible release artifacts from GitHub Actions, not from a developer machine.
- Establish the release artifacts that spec 003 consumes for npm and `npx` distribution.

## Requirements

### Functional Requirements

- **FR1**: `pip install agent-mail-cli`, `pipx install agent-mail-cli`, and `pipx run --spec agent-mail-cli agent-mail describe` work on Linux, macOS, and Windows for Python 3.10+.
- **FR2**: After install, `agent-mail` is available on PATH even though the PyPI distribution name is `agent-mail-cli`.
- **FR3**: Each tagged release attaches a wheel, an sdist, and four PyInstaller binaries to the GitHub Release.
- **FR4**: `winget install JuanjoFuchs.agent-mail-cli` installs `agent-mail` on Windows after the WinGet manifest is approved.
- **FR5**: Installed packages and release binaries preserve all behavior specified by spec 001.
- **FR6**: Packaged installs use `~/.agent-mail/mail.db` as the default database path, resolved from the user's home directory. `AGENT_MAIL_DB` remains the only override mechanism.

### Non-Functional Requirements

- **NFR1**: All release artifacts are built and uploaded by GitHub Actions.
- **NFR2**: After the first release, PyPI uploads use Trusted Publishing (OIDC). Long-lived PyPI API tokens are not used for steady-state publishing.
- **NFR3**: The release version is authored in exactly one place and tag-pushed releases fail before artifact creation when the tag disagrees with that version.

### Technical Constraints

- **TC1**: Source distribution requires Python 3.10+. PyInstaller binaries do not require Python on the user's machine.
- **TC2**: PyPI distribution name is `agent-mail-cli`; Python import name is `agent_mail`; console command is `agent-mail`.
- **TC3**: The console-script entry point exposes the same CLI as spec 001.
- **TC4**: PyInstaller `--onefile` is used for release binaries.
- **TC5**: Platform binary matrix:

  | Platform | Architecture | Runner | Binary suffix |
  |---|---|---|---|
  | Windows | x64 | `windows-latest` | `windows-x64.exe` |
  | Linux | x64 | `ubuntu-latest` | `linux-x64` |
  | macOS | x64 | `macos-13` | `darwin-x64` |
  | macOS | arm64 | `macos-latest` | `darwin-arm64` |

- **TC6**: Default database path resolves to `~/.agent-mail/mail.db` via the user's home directory.
- **TC7**: `AGENT_MAIL_DB` override semantics from spec 001 are unchanged.
- **TC8**: WinGet package identifier is `JuanjoFuchs.agent-mail-cli`.

### Requirement Traceability

| Requirement | Acceptance Criteria |
|---|---|
| FR1 | AC6, AC7, AC8 |
| FR2 | AC6, AC7, AC8, AC10 |
| FR3 | AC1, AC3 |
| FR4 | AC9, AC10, AC11 |
| FR5 | AC4, AC5 |
| FR6 | AC12, AC13 |
| NFR1 | AC3, AC9, AC15, AC16 |
| NFR2 | AC15, AC16 |
| NFR3 | AC14 |
| TC1 | AC6, AC7, AC8, AC10 |
| TC2 | AC1, AC6, AC7, AC8 |
| TC3 | AC4, AC5 |
| TC4 | AC3, AC5 |
| TC5 | AC3 |
| TC6 | AC12 |
| TC7 | AC13 |
| TC8 | AC9, AC10, AC11 |

## Pre-requisites (Human Required)

These must be completed before the implementation can publish successfully. GitHub-side setup may be done from the agent session with JJ's approval and credentials. PyPI and token creation steps require the relevant web UI.

### PyPI account, name reservation, and first-release token

> **Known gotcha from ccburn:** PyPI's pending-publisher flow may fail for a first upload. The reliable path is to use a one-time API token for the first release, verify the pending publisher activates, then remove token-based publishing.

- [x] PyPI account exists at https://pypi.org.
- [x] Project name `agent-mail-cli` reserved on PyPI via Pending Trusted Publisher.
- [x] Pending Trusted Publisher configured for:
  - Owner: `JuanjoFuchs`
  - Repository: `agent-mail-cli`
  - Workflow: `release.yml`
  - Environment: `release`
- [x] PyPI API token generated and stored locally in `.env` as `PYPI_API_TOKEN`.
- [x] Push `PYPI_API_TOKEN` to the repository secret for the first release only.
- [ ] After the first release succeeds and `https://pypi.org/project/agent-mail-cli/` is live:
  - [ ] Confirm the PyPI publisher is active, not pending.
  - [ ] Remove the token fallback from the release workflow.
  - [ ] Delete the `PYPI_API_TOKEN` repository secret.

### GitHub repository setup

- [x] Create the `release` environment.

### WinGet token

- [ ] Generate a GitHub Personal Access Token with `public_repo` scope.
- [x] Add it as the `WINGET_TOKEN` repository secret.

### Initial WinGet submission trigger

- [ ] After the first GitHub Release includes a Windows EXE, trigger the one-time WinGet submission workflow for version `0.1.0`.
- [ ] Verify the generated WinGet PR includes `UpgradeBehavior: uninstallPrevious` before Microsoft review.

## Key Decisions

### Package form

The implementation moves from a single script to an installable Python package while preserving the CLI behavior specified in spec 001. The package must support a console command and `python -m agent_mail`.

### Dist name and command name differ

PyPI rejected `agent-mail`, so the PyPI distribution is `agent-mail-cli`. The command name, GitHub Release binary name, WinGet command alias, and spec 003 npm command remain `agent-mail`. This preserves the user-facing interface while satisfying PyPI's naming rules.

### First PyPI deploy uses a temporary token

A Pending Trusted Publisher is configured before release, but the first upload uses `PYPI_API_TOKEN` because ccburn hit first-upload failures with pending publishers. After the first upload, the publisher must be verified as active, token-based publishing removed from the workflow, and the secret deleted.

### WinGet upgrade behavior is explicit

The WinGet portable installer manifest must include `UpgradeBehavior: uninstallPrevious`. Without it, upgrades can leave duplicate installed versions. The submission workflow may inject the field, but AC9 verifies the submitted manifest rather than trusting the workflow implementation.

### Stable packaged database path

The original default database location was `mail.db` next to the script. Packaged installs cannot use that location because pipx environments and portable installer directories are not durable user state. Packaged installs default to `~/.agent-mail/mail.db`; `AGENT_MAIL_DB` remains the only override.

### No automatic legacy database migration

The packaged CLI does not search for or import legacy `mail.db` files from other locations. Migration is documented as a manual copy operation.

### Single source of truth for version

The project version is authored once in package metadata. Release tags, file names, and release titles derive from or validate against that version.

### ccburn is the implementation reference

ccburn (`D:/jfuchs/dev/ccburn`) is the working precedent for PyPI, GitHub Release binaries, and WinGet automation. The implementer reads ccburn's package metadata and workflows, then adapts names, package identifiers, binary names, and dependencies for Agent Mail. This spec defines the contracts; ccburn provides the proven implementation pattern.

## Implementation Tasks

### Python packaging

- [ ] Convert the CLI into an installable `agent_mail` package while preserving spec 001 behavior.
- [ ] Expose `agent-mail` as the console command.
- [ ] Support `python -m agent_mail`.
- [ ] Change the packaged default database path to `~/.agent-mail/mail.db`.
- [ ] Keep `AGENT_MAIL_DB` as the only database path override.

### Package metadata

- [ ] Add package metadata for `agent-mail-cli`, Python 3.10+, MIT license, repository URL, and the `agent-mail` script entry.
- [ ] Keep runtime dependencies empty unless implementation proves one is required.
- [ ] Verify the built wheel filename uses PyPI's normalized `agent_mail_cli` prefix.

### Tests

- [ ] Add automated coverage for every spec 001 acceptance criterion.
- [ ] Add parity coverage that runs each command through the importable Python package and the PyInstaller binary, comparing stdout JSON, stderr JSON where applicable, and exit codes.
- [ ] Isolate mailbox state per test with `AGENT_MAIL_DB`.

### CI/CD workflows

- [ ] Add CI for lint, test, and build validation.
- [ ] Add a release workflow that validates the tag against package metadata before building artifacts.
- [ ] Publish wheel and sdist to PyPI from GitHub Actions.
- [ ] Build and attach the four platform binaries listed in TC5 to the GitHub Release.
- [ ] Add WinGet initial-submission and follow-up publish workflows using the `JuanjoFuchs.agent-mail-cli` identifier.
- [ ] Ensure the WinGet submission manifest contains `UpgradeBehavior: uninstallPrevious`.

### Documentation sweep

- [ ] Update `README.md` install instructions for `pipx install agent-mail-cli`, `pipx run --spec agent-mail-cli agent-mail describe`, direct GitHub Release binaries, and `winget install JuanjoFuchs.agent-mail-cli` after Microsoft approval.
- [ ] Document the manual legacy database migration copy.
- [ ] Update `AGENTS.md` and `PROJECT_UNDERSTANDING.md` if the source layout changes.

### First release

- [ ] Set the first release version to `0.1.0`.
- [ ] Push tag `v0.1.0` after JJ approves the implementation.
- [ ] Verify GitHub Release artifacts, PyPI publication, and clean-machine `pipx` install.
- [ ] Complete the PyPI Trusted Publishing cleanup described in the prerequisites.
- [ ] Trigger the initial WinGet submission and monitor the Microsoft PR until approval or rejection.

## Acceptance Criteria

### Build artifacts

- [ ] **AC1**: `python -m build` produces `dist/agent_mail_cli-X.Y.Z-py3-none-any.whl` and `dist/agent_mail_cli-X.Y.Z.tar.gz` for the package metadata version.
- [ ] **AC2**: `twine check dist/*` passes.
- [ ] **AC3**: After a successful tag push, the GitHub Release for that tag has six artifacts: `.whl`, `.tar.gz`, and four platform binaries.

### Source parity

- [ ] **AC4**: All spec 001 acceptance criteria (AC1-AC46) pass against the installed `agent-mail` command.
- [ ] **AC5**: Parity tests run each spec 001 command through both the importable package and the PyInstaller binary, asserting identical stdout JSON, stderr JSON where applicable, and exit codes.

### PyPI

- [ ] **AC6**: `pip install agent-mail-cli` on clean Python 3.10+ environments on Linux, macOS, and Windows makes `agent-mail` available on PATH.
- [ ] **AC7**: `pipx install agent-mail-cli && agent-mail describe` returns the documented schema on Linux, macOS, and Windows.
- [ ] **AC8**: `pipx run --spec agent-mail-cli agent-mail describe` works without persistent install.

### WinGet

- [ ] **AC9**: The initial WinGet workflow opens a PR to `microsoft/winget-pkgs`; the submitted installer manifest contains `UpgradeBehavior: uninstallPrevious`.
- [ ] **AC10**: After Microsoft approval, `winget install JuanjoFuchs.agent-mail-cli` installs the binary on a clean Windows x64 machine and `agent-mail describe` runs from any working directory.
- [ ] **AC11**: After a subsequent release and WinGet publish run, `winget upgrade JuanjoFuchs.agent-mail-cli` does not leave duplicate entries; `winget list agent-mail-cli` returns exactly one row.

### Storage

- [ ] **AC12**: First invocation of the packaged command creates `~/.agent-mail/mail.db` with the schema documented in spec 001 TC9.
- [ ] **AC13**: `AGENT_MAIL_DB=<path> agent-mail ...` directs all reads and writes to `<path>`; `~/.agent-mail/mail.db` is not created or modified.

### Versioning and trusted publishing

- [ ] **AC14**: Pushing tag `vX.Y.Z` with a value that differs from the package metadata version fails the release workflow before artifact creation.
- [ ] **AC15**: The first release publishes to PyPI using `PYPI_API_TOKEN`; after upload, `https://pypi.org/project/agent-mail-cli/` is live and PyPI shows the publisher promoted from pending to active.
- [ ] **AC16**: After `PYPI_API_TOKEN` is removed and token-based workflow configuration is deleted, the next release publishes through OIDC without a password field in the PyPI publish step.

## Testing Approach

### Local validation

Run before pushing a release tag:

```bash
ruff check src/ tests/
pytest
python -m build
twine check dist/*
pipx install ./dist/agent_mail_cli-*.whl --force
agent-mail describe
```

Expected result: lint, tests, build, package checks, local wheel install, and `agent-mail describe` all succeed.

### CI gates

Every PR and `main` push runs CI for lint, tests, and build validation. A failed CI run blocks release work until fixed.

### Release validation

After pushing `vX.Y.Z`:

```bash
gh run watch
gh release view vX.Y.Z
pip index versions agent-mail-cli
```

Expected result: release workflow succeeds, six artifacts are attached to the GitHub Release, and the version is visible on PyPI.

### Clean-machine verification

- Linux or macOS clean environment: `pipx run --spec agent-mail-cli agent-mail describe`.
- Windows clean environment: `pipx install agent-mail-cli && agent-mail describe`.
- After WinGet approval: `winget install JuanjoFuchs.agent-mail-cli`, then `agent-mail describe`.
- After the next release: `winget upgrade JuanjoFuchs.agent-mail-cli`, then confirm `winget list agent-mail-cli` returns one row.

### Human-in-the-Loop Release Protocol

1. **Agent**: Finish implementation and pass local validation.
2. **Agent**: Ask JJ before pushing the release tag.
3. **Human**: Approves the release tag.
4. **Agent**: Pushes the tag and monitors GitHub Actions.
5. **Agent**: Reports PyPI and GitHub Release status.
6. **Human**: Confirms PyPI Trusted Publisher status in the PyPI web UI if the agent cannot access it.
7. **Agent**: Removes token-based publishing and deletes the repository secret after confirmation.
8. **Agent**: Triggers WinGet submission.
9. **Human**: Confirms clean Windows and Microsoft Store/WinGet validation steps when local agent access is unavailable.

## Usage Examples

```bash
pipx install agent-mail-cli
agent-mail describe
```

```bash
pipx run --spec agent-mail-cli agent-mail describe
```

```bash
winget install JuanjoFuchs.agent-mail-cli
agent-mail describe
```

Manual legacy database migration:

```bash
mkdir -p ~/.agent-mail
cp /path/to/legacy/mail.db ~/.agent-mail/mail.db
```

## Out of Scope

- npm distribution and `npx` behavior; covered by spec 003.
- Linux arm64 binaries.
- Homebrew, conda, deb, rpm, or other package managers.
- TestPyPI and pre-release channels.
- Automatic legacy database migration.
- A `--migrate` command.
- New Agent Mail CLI behavior beyond the packaged default database path.
- Telemetry, update checks, or network calls from the CLI itself.

## References

- spec 001: [`specs/001-agent-mail-cli.md`](001-agent-mail-cli.md) — behavioral contract this packaging must preserve.
- spec 003: [`specs/003-npm-distribution.md`](003-npm-distribution.md) — npm distribution that consumes these release binaries.
- ccburn implementation reference: `D:/jfuchs/dev/ccburn` — package metadata and GitHub workflows for CI, release, and WinGet.
- PyPI Trusted Publishing: https://docs.pypi.org/trusted-publishers/.
- WinGet `wingetcreate`: https://learn.microsoft.com/en-us/windows/package-manager/package/windows-package-manager-manifest-creator.
- Project context: [PROJECT_UNDERSTANDING.md](../PROJECT_UNDERSTANDING.md).
