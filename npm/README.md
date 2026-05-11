# Agent Mail CLI

A self-describing local inbox for coding agents.

## Usage

```bash
npx -y agent-mail-cli describe
```

Or install globally:

```bash
npm install -g agent-mail-cli
agent-mail describe
```

## Requirements

- Node.js 16 or newer
- Supported platform: Windows x64, Linux x64, macOS x64, or macOS arm64

The npm package downloads the matching standalone binary from the Agent Mail
GitHub Release during install. Python is not required.

## Alternative Installation

If npm installation fails or your platform is not supported by the npm binary
wrapper, install the Python package with pipx:

```bash
pipx install agent-mail-cli
agent-mail describe
```

## Links

- [GitHub](https://github.com/JuanjoFuchs/agent-mail-cli)
- [PyPI](https://pypi.org/project/agent-mail-cli/)

## License

MIT
