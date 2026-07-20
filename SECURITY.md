# Security Policy

Discord MCP Bridge is a local MCP server that uses a Discord bot token to call the Discord REST API.

## Supported Versions

Security fixes are currently handled on the `main` branch until the project starts publishing multiple maintained release lines.

## Reporting a Vulnerability

Please report security issues privately before opening a public issue. If GitHub private vulnerability reporting is enabled for this repository, use that flow. Otherwise, contact the maintainer directly and include:

- a short description of the issue
- affected versions or commits, if known
- reproduction steps
- expected impact

## Token Safety

- Use a Discord bot token only. Do not use Discord user tokens.
- Do not commit `.env` files, real bot tokens, guild allowlists, or channel allowlists that should remain private.
- Prefer `DISCORD_ALLOWED_GUILDS` and `DISCORD_ALLOWED_CHANNELS` for local safety boundaries.
- Grant the bot only the Discord permissions required for the tools you plan to use.
- Rotate the Discord bot token immediately if it is exposed in logs, commits, screenshots, or issue reports.

## Attachment Downloads

- `discord_download_attachment` resolves attachments from a fresh Discord message response instead of accepting an arbitrary caller-provided URL.
- Downloads only use HTTPS Discord attachment CDN hosts and paths, and redirects are rejected.
- CDN requests use a separate HTTP client that never receives the Discord bot authorization header.
- The response is streamed with a default 10 MiB maximum configured through `DISCORD_MAX_ATTACHMENT_BYTES`.
- Set `DISCORD_ALLOWED_ATTACHMENT_MIME_TYPES` to an exact or wildcard MIME allowlist when the MCP client should only receive selected file types.
