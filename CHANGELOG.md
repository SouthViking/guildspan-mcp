# Changelog

All notable changes to this project will be documented in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
style sections and uses conventional commits for commit messages.

## [Unreleased]

### Added

- Read-only tools for bot identity, user lookup, guild member lookup and search, and guild role listing.
- Optional role-name resolution for member lookup and search without adding moderation permissions.
- GitHub Actions CI for pull requests and pushes to `main`.
- Package build verification in CI.
- Public-readiness project metadata, contribution notes, and security guidance.

## [0.1.0] - 2026-07-13

### Added

- Local FastMCP server entrypoint for `discord-mcp-bridge`.
- Discord bot-token REST client over stdio MCP transport.
- Tools for diagnostics, channel listing and lookup, message history, message search, message sending and editing, thread creation, and reactions.
- Local safety controls through `DISCORD_ALLOWED_CHANNELS` and `DISCORD_ALLOWED_GUILDS`.
- Optional actor attribution through `DISCORD_ACTOR_NAME`, `DISCORD_ACTOR_DISCORD_ID`, and `DISCORD_APPEND_ATTRIBUTION`.
- Tests and strict mypy configuration.
