# AGENTS.md for cli-agent-orchestrator

## Overview

CLI Agent Orchestrator (CAO) is an open-source multi-agent orchestration framework for AI coding CLIs. It runs each agent in an isolated tmux session and coordinates them with a supervisor-worker pattern over MCP, so one supervisor agent can delegate tasks to multiple specialist agents in parallel, sequentially, or as a swarm.

## Development

### Setup

```bash
uv sync
```

### Run

```bash
uv run cao
```

### Test

```bash
uv run pytest
```

### Lint

```bash
uv run ruff check .
```

### Type Check

```bash
uv run mypy .
```

## Architecture

- `src/` - Core orchestration framework (Python)
- `web/` - Bundled Web UI for agent management
- `skills/` - Reusable agent skill definitions
- `scripts/` - Utility and automation scripts
- `test/` - Test suite (pytest)

## Deployment

Published as a PyPI package (`cli-agent-orchestrator`). Can be run locally with `uv run cao` or deployed as an MCP management server.
