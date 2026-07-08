# Homebrew Tap — ai-data-platform

Install `adp`, the AI Data Platform CLI, via Homebrew on macOS.

## Prerequisites

- macOS (Apple Silicon or Intel)
- [Homebrew](https://brew.sh) installed

## Install

```bash
brew tap yogi776/tap
brew install ai-data-platform
```

Verify the installation:

```bash
adp --help
adp version
```

## Upgrade

To upgrade to the latest version:

```bash
brew upgrade ai-data-platform
```

## Uninstall

To completely remove the installation:

```bash
brew uninstall ai-data-platform
brew untap yogi776/tap   # optional: remove the tap
```

## MCP Server

The formula installs all optional extras (`[all]`), including the MCP server:

```bash
adp mcp-server --help
```

For MCP client setup (Cursor, Claude Desktop, etc.), see the
[MCP Guide](https://github.com/Yogi776/data-generation-sdk/blob/main/docs/MCP-GUIDE.md).

## Verify the installation

Run these commands to confirm `adp` is correctly on your `PATH`:

```bash
# Should print: ai-data-platform <version>
adp version

# Should show the full command list
adp --help

# MCP subcommand should be available
adp mcp-server --help
```

If `adp` is not found after install, fix your PATH:

```bash
# Force-link if needed
brew link --overwrite ai-data-platform

# Or add Homebrew's bin to your PATH
echo 'export PATH="$(brew --prefix)/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Troubleshooting

### `brew install` fails with PEP 668

This should not happen with the formula — it installs into an isolated virtualenv (`libexec`).
If seen, try:

```bash
brew uninstall ai-data-platform
brew install ai-data-platform
```

### `adp: command not found` after install

Homebrew may not have added itself to your PATH in your current shell.
Start a new terminal session, or run:

```bash
source ~/.zshrc   # or ~/.bashrc
```

Then verify with `which adp` and `adp version`.

### Wrong Python version

The formula depends on `python@3.12`. If you have multiple Python versions,
Homebrew's `python@3.12` is used regardless of system Python. The package
requires Python 3.11+ and works with both Apple Silicon and Intel Macs.

### Upgrade not finding latest version

If `brew upgrade` says "Already up-to-date" but a newer release exists on PyPI:

```bash
brew update
brew upgrade ai-data-platform
```

If it still doesn't work, force-reinstall:

```bash
brew reinstall ai-data-platform
```

## More information

| Resource | Link |
|----------|------|
| Package on PyPI | https://pypi.org/project/ai-data-platform/ |
| Source code | https://github.com/Yogi776/data-generation-sdk |
| Full documentation | https://github.com/Yogi776/data-generation-sdk#readme |
| MCP setup guide | https://github.com/Yogi776/data-generation-sdk/blob/main/docs/MCP-GUIDE.md |

## Uninstall everything cleanly

```bash
# Remove the CLI
brew uninstall ai-data-platform

# Remove the tap
brew untap yogi776/tap

# Remove agent skills installed by adp init (if desired)
rm -rf ~/.cursor/skills/adp-*
```
