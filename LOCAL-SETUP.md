# Local Development Setup

macOS-native instructions for contributors: environment setup, running tests, and MCP IDE configuration.

## Prerequisites

- **Python 3.11+** — use `python3 --version` to check
- **Git** — `git --version`
- A supported MCP client: Cursor, Claude Desktop, Claude Code, Windsurf, or VS Code

## Environment setup

```bash
# Clone the repo
git clone git@github.com:Yogi776/data-generation-sdk.git
cd data-generation-sdk/ai-data-platform

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # zsh/bash — on fish, use `venv/bin/activate.fish`

# Install with all extras (dev, LLM, MCP, DB drivers)
pip install -e ".[dev,all]"

# Verify the CLI works
adp --version
```

## MCP client setup

After `adp init` in a project, run `adp setup-agent --client all` to install MCP configs for all supported clients. See [docs/MCP-GUIDE.md](docs/MCP-GUIDE.md) for full IDE-specific instructions.

## Running tests

```bash
# Unit tests
pytest

# Linter
ruff check .

# Type checker
mypy src
```

## Project structure

```
ai-data-platform/
├── src/ai_data_platform/   # Main package
│   ├── agent/              # Agent setup + workflow prompts
│   ├── agent_skills/       # Cursor skill definitions
│   ├── cli.py              # CLI entry point
│   ├── engine/             # Generation engine (Plan IR → data)
│   ├── mcp/                # MCP server adapter
│   ├── quality/            # Quality check framework
│   ├── sdk.py              # Python SDK
│   └── ...                 # Config, catalog, explorer, profiler
├── docs/                   # Documentation
├── examples/               # Example projects
└── tests/                  # Test suite
```
