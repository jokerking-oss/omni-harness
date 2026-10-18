# OmniHarness 2.0

English | [中文](./README_zh.md)

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](./backend/pyproject.toml)
[![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white)](./Makefile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

OmniHarness is an open-source **super agent harness**. It combines **sub-agents**, **memory** and **sandboxed execution** with extensible **skills**, so agents can complete tasks that range from minutes to hours.

It is not a framework you have to assemble. It ships with what agents actually need �?a filesystem, memory, skills, a sandbox runtime, and the ability to plan and spawn sub-agents for multi-step work �?while staying extensible.

## Core capabilities

- **Sub-Agents** �?split complex work across sub-agents that run in parallel, then aggregate the results. Each has its own context, tools and termination conditions.
- **Sandbox** �?every task runs in an isolated Docker container with a full filesystem (skills / workspace / uploads / outputs). Agents can run commands, read and write files, and work on long-running jobs.
- **Skills** �?structured capability modules, loaded progressively so only what the current step needs enters the context. Extensible, replaceable and composable.
- **Long-term memory** �?preferences and working habits accumulate across sessions, so the agent fits your style and recurring workflows over time.
- **Agentic browser** �?optional browser control that lets an agent actually operate a page: navigate, click, type and submit forms.
- **Scheduled tasks** �?run on `once` / `cron` / `interval` schedules, reusing a conversation or starting a fresh one each run.
- **Projects** �?group related conversations under one name, sharing project instructions and a document shelf.
- **IM channels** �?receive tasks from Telegram, Slack, Feishu/Lark, WeCom, DingTalk and WeChat without a public IP.
- **Terminal UI** �?a TUI that shares the same conversation store as the Web UI.

## Quick start

### Requirements

- Docker Desktop / Docker Engine with **Docker Compose v2.24+**
- Python 3.12+, Node.js 22+
- Or just use Docker (recommended)

### Install

```bash
git clone https://github.com/jokerking-oss/omni-harness.git
cd omni-harness
```

Run the setup wizard (recommended). It walks through model provider, optional search tools and sandbox mode, then generates `config.yaml` and writes `.env`:

```bash
make setup
```

Use `make doctor` at any time to check configuration and system environment.

### Run

**Docker (recommended)**

```bash
make docker-init    # pull sandbox images on first run or after updates
make docker-start   # start services
```

**Local development**

```bash
make check     # verify Node.js 22+, pnpm, uv, nginx
make install   # install backend + frontend dependencies
make dev       # start services
```

Open **http://localhost:2026**.

## Model configuration

OmniHarness is not tied to a specific provider �?any OpenAI-compatible API works. The setup wizard generates a minimal `config.yaml`; a typical provider entry looks like:

```yaml
models:
  - name: gpt-4o
    display_name: GPT-4o
    use: langchain_openai:ChatOpenAI
    model: gpt-4o
    api_key: $OPENAI_API_KEY
```

Put API keys in `.env`:

```bash
OPENAI_API_KEY=your-api-key
```

## Documentation

- [Contributing](CONTRIBUTING.md)
- [Configuration](backend/docs/CONFIGURATION.md)
- [Backend architecture](backend/README.md)

## Security

OmniHarness can **execute system commands and read/write files**. It is designed to run in a **trusted local environment** (loopback access only).

Exposing the agent to an untrusted network �?the public internet or a shared LAN �?without strict protection can lead to unauthorized calls that execute privileged operations, along with the compliance and legal risks that follow.

For cross-network deployments, at minimum:

- **IP allowlisting** �?restrict access to trusted sources with a firewall or `iptables`
- **Front-door authentication** �?put strong auth in front of the service (e.g. nginx)
- **Network isolation** �?keep the agent and trusted devices on a dedicated segment
- **First-run setup** �?on a fresh instance, create the admin account via `/setup` immediately

Treat admin access as equivalent to code execution on the host.

## License

Released under the [MIT License](./LICENSE).
