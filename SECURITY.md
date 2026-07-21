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

## Attachment Uploads

- Local path uploads are disabled until `DISCORD_ALLOWED_UPLOAD_PATHS` lists one or more absolute directory roots.
- Paths are resolved before access. Regular files and symlink targets must remain inside a configured root.
- Public URL uploads require HTTPS without credentials or custom ports. Every host and redirect destination must resolve only to public addresses.
- URL downloads run through a separate HTTP client without the Discord bot authorization header and are streamed under configured limits.
- Base64 is decoded strictly, and all sources are checked against per-file and aggregate request ceilings before Discord receives them.
- Use `DISCORD_ALLOWED_UPLOAD_URL_HOSTS` and `DISCORD_ALLOWED_UPLOAD_MIME_TYPES` to narrow outgoing sources and file types when operating in a sensitive environment.
- Grant `ATTACH_FILES` only when file sending is needed, and remember that any allowed local file can be sent to any Discord channel permitted by the channel/guild policy.
