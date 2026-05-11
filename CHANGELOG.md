# Changelog

All notable changes to Agent Mail CLI will be documented in this file.

## Unreleased

- Update public documentation as package channels settle.

## [0.1.4] - 2026-05-11

### Added

- Published `@juanjofuchs/agent-mail@0.1.4` to npm through GitHub Actions
  Trusted Publishing.
- Added the `agent-mail-cli` npm bin alias alongside the primary `agent-mail`
  command.
- Added cross-platform npm smoke verification for Windows x64, Linux x64,
  macOS x64, and macOS arm64 on Node 16.

### Changed

- Kept npm distribution scoped as `@juanjofuchs/agent-mail` after npm rejected
  both unscoped package names: `agent-mail` and `agent-mail-cli`.
- Updated spec 003 and project docs with the verified npm publishing path.

## [0.1.3] - 2026-05-11

### Added

- Added the npm wrapper package for `npx -y @juanjofuchs/agent-mail describe`.
- Added npm postinstall download of the matching GitHub Release binary.
- Added `npm-publish.yml` and `npm-smoke.yml` workflows.

### Fixed

- Rebuilt the Linux release binary on `ubuntu-22.04` so npm-installed binaries
  run on the target Linux baseline without requiring newer glibc.
- Excluded downloaded binaries from the npm tarball so npm ships only wrapper
  code and metadata.

## [0.1.2] - 2026-05-08

### Changed

- Switched steady-state PyPI releases to Trusted Publishing after the first
  token-based bootstrap publish created the project.
- Removed the temporary PyPI API token fallback from the release workflow.

### Fixed

- Added WinGet manifest schema headers and submitted the exact manifest
  directory expected by `wingetcreate`.

## [0.1.1] - 2026-05-08

### Added

- Published GitHub Release assets: wheel, sdist, and standalone binaries for
  Windows x64, Linux x64, macOS x64, and macOS arm64.
- Published `agent-mail-cli` on PyPI with the `agent-mail` console command.
- Added WinGet initial submission automation and opened the Microsoft review PR.

### Fixed

- Switched the macOS Intel release job to a supported GitHub Actions runner.

## [0.1.0] - 2026-05-08

### Added

- Converted the single-script CLI into the installable `agent_mail` Python
  package.
- Added the `agent-mail` console command and `python -m agent_mail` entry point.
- Added CI, release packaging, PyInstaller binary builds, and WinGet workflow
  scaffolding.
- Added spec 001 behavior coverage, package parity tests, and isolated
  `AGENT_MAIL_DB` test state.
- Changed packaged default mailbox storage to `~/.agent-mail/mail.db`.

## Pre-release

### Added

- Seeded the repository with project instructions, product understanding,
  behavioral specs, and the extracted Agent Mail CLI source.
