# Contributing

Thanks for improving Discord MCP Bridge.

## Development Setup

This project supports Python 3.11 and newer.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Run the main checks before opening a pull request:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m mypy src tests
.venv/bin/python -m build
```

## Pull Requests

- Keep changes focused and include tests for new behavior.
- Update `README.md` when tool inputs, configuration, or client setup changes.
- Update `CHANGELOG.md` under `Unreleased` for user-visible changes.
- Do not commit real Discord tokens, `.env` files, private guild IDs, or private channel IDs.

## Commit Messages

Use conventional commit style when practical, for example:

- `feat: add discord delete message tool`
- `fix: validate thread archive duration`
- `docs: clarify codex mcp setup`
