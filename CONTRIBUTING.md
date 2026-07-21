# Contributing

Thanks for improving GuildSpan.

## Development Setup

CI tests Python 3.11 through 3.14. Use any of those versions for local development.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pre_commit install
```

Run the same quality gates used by CI before opening a pull request:

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src tests
.venv/bin/python -m pytest --cov=guildspan --cov-branch --cov-report=term-missing
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
.venv/bin/python -m check_wheel_contents dist/*.whl
.venv/bin/python -m pre_commit run --all-files
```

Ruff can apply safe lint fixes and formatting with:

```bash
.venv/bin/python -m ruff check --fix src tests
.venv/bin/python -m ruff format src tests
```

## Pull Requests

- Keep changes focused and include tests for new behavior.
- Update `README.md` when tool inputs, configuration, or client setup changes.
- Update `CHANGELOG.md` under `Unreleased` for user-visible changes.
- Do not commit real Discord tokens, `.env` files, private guild IDs, or private channel IDs.

## Versioning and Changelog

- GuildSpan follows semantic versioning while the public interface evolves.
- `src/guildspan/__init__.py` is the single source for `__version__`; Hatch reads package metadata from it.
- Add user-visible changes under `Unreleased` in `CHANGELOG.md`.
- Release preparation moves those entries into a dated version section and restores an empty `Unreleased` section.
- The package version, Git tag, GitHub Release, PyPI version, and future MCP Registry version must match.

## Commit Messages

Use conventional commit style when practical, for example:

- `feat: add discord delete message tool`
- `fix: validate thread archive duration`
- `docs: clarify codex mcp setup`
