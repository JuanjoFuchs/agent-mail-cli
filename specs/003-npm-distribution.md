---
id: "003"
title: Agent Mail npm Distribution
status: in_progress
blocked_by: ["002"]
blocks: []
---

# Agent Mail npm Distribution

## Overview

Distribute Agent Mail through npm so users without Python — primarily Node-ecosystem coding-agent users — can run `npx -y agent-mail` and get the same tool. The npm package is a thin Node wrapper that downloads the platform binary built in spec 002 and invokes it. Pattern is taken wholesale from ccburn (`D:/jfuchs/dev/ccburn/npm/`).

> **Completion rule:** This spec is not complete until `npx -y agent-mail describe` works on a clean machine for each supported platform — Windows x64, Linux x64, macOS x64, and macOS arm64 — with only Node 16+ installed and zero Python. CI-only verification is insufficient.

## Goals

- `npx -y agent-mail describe` works first-try on a fresh machine with Node 16+.
- npm package version is always identical to the GitHub Release version it depends on (no human edits two files).
- A user on an unsupported platform gets a clear `pipx install agent-mail-cli` fallback hint, not a cryptic error.

## Requirements

### Functional Requirements

- **FR1**: `npx -y agent-mail describe` runs on Windows x64, Linux x64, macOS x64, and macOS arm64 with Node 16+ installed.
- **FR2**: `npm install -g agent-mail` followed by `agent-mail describe` works (the binary is downloaded during install and added to the npm bin directory).
- **FR3**: The npm `postinstall` step downloads the platform-matching binary from the GitHub Release whose tag matches the npm package version, and saves it next to the bin wrapper.
- **FR4**: The bin wrapper spawns the downloaded binary with all CLI arguments forwarded verbatim, inherits stdio, and propagates the binary's exit code.
- **FR5**: On unsupported platforms, the postinstall script exits non-zero with a JSON-style error that hints at `pipx install agent-mail-cli` as a fallback.
- **FR6**: The npm package version is updated to match the GitHub Release tag at publish time by the npm publish workflow. The version in `npm/package.json` is not authored by hand for releases.

### Non-Functional Requirements

- **NFR1**: Steady-state publishing happens in GitHub Actions through npm Trusted Publishing. The first npm publish may be bootstrapped from a developer machine with interactive npm login only if npm requires the package to exist before Trusted Publishing can be configured.
- **NFR2**: The npm-distributed binary's behavior is identical to the PyPI-distributed binary (parity-tested against spec 001's full AC suite).
- **NFR3**: The publish workflow fails fast if any of the four platform binaries is missing from the GitHub Release.

### Technical Constraints

- **TC1**: npm package name is `agent-mail` (same as PyPI name and CLI command).
- **TC2**: `engines.node` is `>=16.0.0`.
- **TC3**: `os` whitelist: `darwin`, `linux`, `win32`. `cpu` whitelist: `x64`, `arm64`. `linux-arm64` is reachable by these whitelists but is not a supported binary in v1; the postinstall script handles that case explicitly.
- **TC4**: The postinstall script is pure Node (no shell scripts, no PowerShell, no Python) so it works identically on every platform.
- **TC5**: Binary is fetched over HTTPS from `https://github.com/JuanjoFuchs/agent-mail-cli/releases/download/v<version>/agent-mail-<version>-<platform>-<arch>[.exe]`.
- **TC6**: npm publishing uses OIDC Trusted Publishing with Node 24 and npm 11+ in GitHub Actions. No long-lived npm token is used for steady-state publishing.

## Pre-requisites (Human Required)

These must be done before the publish workflow can succeed.

### npm account and trusted publisher

- [ ] npm account exists at https://www.npmjs.com.
- [x] Verify the package name is available: `npm view agent-mail` should 404.
- [ ] Bootstrap-publish the first npm version if npm requires the package to exist before Trusted Publishing can be configured.
- [ ] Configure npm Trusted Publishing for package `agent-mail`:
  - Owner: `JuanjoFuchs`
  - Repository: `agent-mail-cli`
  - Workflow: `npm-publish.yml`
- [ ] Confirm no long-lived `NPM_TOKEN` repository secret is required for steady-state publishing.

## Key Decisions

### Single npm package with runtime platform detection

The alternative pattern (esbuild-style: one main package plus one platform-specific package per binary) avoids downloading the wrong binary at install time but adds five npm packages to maintain. ccburn chose the single-package pattern; agent-mail follows. Revisit if install times become a real complaint.

### Binary lives in GitHub Releases, not in the npm package

The npm tarball ships only the wrapper scripts. The binary is fetched from the matching GitHub Release at install time. This keeps the npm package small and avoids embedding the same binary in npm and GitHub Releases.

### Node 16 minimum

Floor for stable `https.get` redirect handling and `fs.promises`. Older Node may work but isn't tested. Same floor as ccburn.

### Unsupported-platform fallback to pipx, not auto-install

If the user is on an unsupported platform (e.g. Linux arm64), postinstall errors with a clear `pipx install agent-mail-cli` hint and exits. The script does not attempt to install Python or invoke pipx itself — that would be silent magic on the user's system.

### First npm publish may be a bootstrap exception

npm Trusted Publishing is configured from package settings. If npm does not expose settings until the package exists, the first `agent-mail` publish may be done from a developer machine using interactive npm login. That exception exists only to create the package. After the package exists, Trusted Publishing is configured and future publishes go through GitHub Actions.

### Reference ccburn instead of inlining files

The wrapper layout (`npm/{package.json,bin/<name>.js,scripts/postinstall.js,README.md,.npmignore}`) and the publish workflow are taken verbatim from `D:/jfuchs/dev/ccburn/npm/` and `D:/jfuchs/dev/ccburn/.github/workflows/npm-publish.yml`. The implementer copies these and substitutes names. This spec defines the contracts and decisions; ccburn defines the structure.

## Architecture

```text
┌───────────────────────┐    ┌──────────────────┐    ┌──────────────────────┐
│ npx -y agent-mail     │───▶│ postinstall.js   │───▶│ GitHub Releases      │
│ npm install -g …      │    │ detect platform  │    │ download binary      │
└───────────────────────┘    └──────────────────┘    └──────────────────────┘
                                       │
                                       ▼
                              ┌────────────────────┐    ┌──────────────────────┐
                              │ bin/agent-mail.js  │───▶│ agent-mail binary    │
                              │ spawn binary       │    │ (PyInstaller)         │
                              └────────────────────┘    └──────────────────────┘
```

## Implementation Tasks

### npm wrapper

- [x] Create the `npm/` directory and copy `D:/jfuchs/dev/ccburn/npm/` as the structural template. Adapt every reference to `ccburn` → `agent-mail`. Specifically:
  - `npm/package.json` — name, description, keywords, `bin` mapping (`agent-mail`), repository URL.
  - `npm/bin/agent-mail.js` — find the binary whose name starts with `agent-mail-` and (on Windows) ends with `.exe`.
  - `npm/scripts/postinstall.js` — `REPO = "JuanjoFuchs/agent-mail-cli"`; binary name format `agent-mail-<version>-<platform-arch suffix>`; fallback hint text mentions `pipx install agent-mail-cli`.
  - `npm/README.md` — install/usage examples for `agent-mail`.
  - `npm/.npmignore` — same structure as ccburn's.
- [x] Verify locally: `cd npm && npm pack` produces a valid tarball. Inspect the tarball contents (`tar -tzf agent-mail-*.tgz`) to confirm only `bin/`, `scripts/`, `README.md`, and `LICENSE` are included.
- [ ] Verify the downloaded Linux release binary runs on the target Linux baseline. `v0.1.2` failed on Ubuntu 22.04-era glibc with `GLIBC_2.38 not found`, so the Linux release runner must use `ubuntu-22.04` or older before npm Linux verification can pass.

## Verification Record

- [x] `npm view agent-mail version` returns 404, so the npm package name is currently available.
- [x] `npm pack` succeeds with a tarball containing only `LICENSE`, `README.md`, `bin/agent-mail.js`, `scripts/postinstall.js`, and `package.json`.
- [x] `node --check npm/bin/agent-mail.js` passes.
- [x] `node --check npm/scripts/postinstall.js` passes.
- [x] Unsupported-platform error helper returns JSON mentioning `pipx install agent-mail-cli`.
- [x] `node npm/bin/agent-mail.js describe` works when the wrapper points at a local compatible PyInstaller binary.
- [x] `tests/test_parity.py` passes comparing module, PyInstaller binary, and npm wrapper when both local binary paths are available.
- [x] `AGENT_MAIL_RUNNER=npm pytest tests/test_cli_behavior.py` passes against the npm wrapper when it points at a local compatible PyInstaller binary.
- [ ] `node npm/scripts/postinstall.js` downloads a live Linux release binary that runs on this host. Blocked until the next release is built with the `ubuntu-22.04` Linux runner.
- [ ] npm Trusted Publishing configured on npmjs.com for `.github/workflows/npm-publish.yml`.
- [ ] npm package published and verified with `npm view agent-mail@<version> version`.

### Publish workflow

- [x] Create `.github/workflows/npm-publish.yml`. Source: `D:/jfuchs/dev/ccburn/.github/workflows/npm-publish.yml`. Adapt:
  - The release-asset verification step lists the four expected agent-mail binary names.
  - `working-directory: npm`.
  - The version-bump step uses `npm version <release-tag-version> --no-git-tag-version`.
  - Publishing uses npm OIDC Trusted Publishing with `--provenance` and no `NODE_AUTH_TOKEN`.

### Documentation sweep

- [x] Update `README.md` install section to lead with `npx -y agent-mail describe` (the spec 001 product wedge), with `pipx install agent-mail-cli` as the secondary path for users who prefer Python tooling.

## Acceptance Criteria

### Publishing

- [ ] **AC1**: After a successful GitHub Release that includes all four platform binaries, `npm-publish.yml` succeeds and `npm view agent-mail@<version> version` returns the published version.
- [ ] **AC2**: If any of the four platform binaries is missing from the GitHub Release, `npm-publish.yml` fails before calling `npm publish` (verified by removing one binary from a test release and observing the failure mode).
- [ ] **AC3**: `npm/package.json`'s version after the publish workflow runs equals the GitHub Release tag (verified by inspecting the published tarball with `npm view agent-mail@<version>`).

### Install on supported platforms

- [ ] **AC4**: `npx -y agent-mail describe` works on a clean Windows x64 machine with Node 16+ and zero Python.
- [ ] **AC5**: `npx -y agent-mail describe` works on a clean Linux x64 machine with Node 16+ and zero Python.
- [ ] **AC6**: `npx -y agent-mail describe` works on a clean macOS x64 machine with Node 16+ and zero Python.
- [ ] **AC7**: `npx -y agent-mail describe` works on a clean macOS arm64 machine with Node 16+ and zero Python.
- [ ] **AC8**: `npm install -g agent-mail && agent-mail describe` works (binary lands in the npm bin directory and is on PATH).

### Unsupported platforms

- [ ] **AC9**: On a platform not in the supported set (e.g. Linux arm64), the postinstall script exits non-zero with stderr output that mentions `pipx install agent-mail-cli` as the fallback.

### Parity

- [ ] **AC10**: All spec 001 acceptance criteria (AC1–AC46) pass when the test runner targets `npx -y agent-mail` instead of the source script.
- [x] **AC11**: `tests/test_parity.py` (introduced in spec 002) is extended to compare three call sites for each command — imported source, PyInstaller binary directly, and the npm-wrapped invocation — and asserts identical stdout JSON and exit codes across all three.

## Testing Approach

### Local validation before publish

```bash
cd npm
npm pack
node scripts/postinstall.js          # downloads binary
node bin/agent-mail.js describe      # invokes wrapper end-to-end
```

A successful local run confirms the wrapper logic before any tag is pushed.

### Clean-machine verification (post-publish)

For each supported platform — Windows x64, Linux x64, macOS x64, macOS arm64 — provision a fresh environment with Node 16+ and zero Python. Run:

```bash
npx -y agent-mail describe
```

Expected: documented JSON schema on stdout, exit 0. Record the version of Node and the npm version that resolved.

### Unsupported-platform manual test

On a Linux arm64 host (or under QEMU), run `npm install -g agent-mail` and verify postinstall exits non-zero with the documented fallback hint.

## Out of Scope

- Platform-specific npm packages (esbuild-style split into `@agent-mail/cli` plus per-platform packages).
- Linux arm64 binary — covered by spec 002's Out of Scope.
- Pre-release npm tags (`@beta`, `@next`) and dist-tag automation.
- Bundling Python or pipx into the npm package as a fallback (would defeat the "no Python required" goal).
- Telemetry or update-check pings from the postinstall script.

## References

- spec 001: [`specs/001-agent-mail-cli.md`](001-agent-mail-cli.md) — behavioral contract.
- spec 002: [`specs/002-packaging.md`](002-packaging.md) — produces the binaries this package consumes.
- ccburn npm wrapper: `D:/jfuchs/dev/ccburn/npm/` and `D:/jfuchs/dev/ccburn/.github/workflows/npm-publish.yml`. The implementer reads these and adapts.
- Project context: [PROJECT_UNDERSTANDING.md](../PROJECT_UNDERSTANDING.md).
