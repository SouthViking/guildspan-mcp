# Changelog

All notable changes to this project will be documented in this file.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
style sections and uses conventional commits for commit messages.

## [Unreleased]

### Changed

- Adopted GuildSpan as the project, package, executable, MCP server, and message-attribution brand.
- Message attribution now places the configured actor above the message body and keeps the configurable `sent using GuildSpan` brand footer below it.
- `discord_send_message` now accepts optional text, attachments, and native sticker IDs for text-only, media-only, sticker-only, and combined messages.

### Added

- Secure outgoing attachment sources for explicitly allowed local paths, public HTTPS URLs, and base64 data, with MIME, count, per-file, and aggregate limits.
- Upload policy controls through `DISCORD_ALLOWED_UPLOAD_PATHS`, `DISCORD_ALLOWED_UPLOAD_URL_HOSTS`, `DISCORD_MAX_UPLOAD_BYTES`, `DISCORD_MAX_UPLOAD_TOTAL_BYTES`, and `DISCORD_ALLOWED_UPLOAD_MIME_TYPES`.
- Rich message-history output for attachment details, embed images/thumbnails/videos, stickers, polls, and components.
- `discord_download_attachment` for bounded, MIME-validated Discord CDN downloads returned as native MCP content.
- Attachment download controls through `DISCORD_MAX_ATTACHMENT_BYTES` and `DISCORD_ALLOWED_ATTACHMENT_MIME_TYPES`.
- Read-only tools for bot identity, user lookup, guild member lookup and search, and guild role listing.
- Optional role-name resolution for member lookup and search without adding moderation permissions.
- GitHub Actions CI for pull requests and pushes to `main`.
- Package build verification in CI.
- Public-readiness project metadata, contribution notes, and security guidance.

## [0.1.0] - 2026-07-13

### Added

- Local FastMCP server entrypoint for `guildspan`.
- Discord bot-token REST client over stdio MCP transport.
- Tools for diagnostics, channel listing and lookup, message history, message search, message sending and editing, thread creation, and reactions.
- Local safety controls through `DISCORD_ALLOWED_CHANNELS` and `DISCORD_ALLOWED_GUILDS`.
- Optional actor attribution through `DISCORD_ACTOR_NAME`, `DISCORD_ACTOR_DISCORD_ID`, and `DISCORD_APPEND_ATTRIBUTION`.
- Tests and strict mypy configuration.
