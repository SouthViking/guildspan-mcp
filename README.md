# Discord MCP Bridge

[![CI](https://github.com/SouthViking/discord-mcp-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/SouthViking/discord-mcp-bridge/actions/workflows/ci.yml)

Discord MCP Bridge is a local MCP server that exposes Discord bot actions to AI coding clients such as Codex, Claude, Cursor, and other MCP-capable tools.

It supports Discord diagnostics, channel inspection, read-only user/member/role lookup, rich message and media inspection, secure attachment downloads, message search, sending and editing bot messages, creating threads, and adding reactions through the official Discord REST API using a bot token.

It is not a hosted service or marketplace plugin. It is a local MCP server that runs on the user's machine and is registered in an MCP-capable client.

## AI Client Quickstart

If you are connecting this repo from an AI editor or assistant, treat it as a **local MCP server project**.

You can give an AI coding agent this prompt:

```text
Install this repository as a local MCP server named discord-mcp-bridge.
Do not treat it as a marketplace plugin. Create a Python virtual environment,
install the project in editable mode, register the MCP command in my client
config, set DISCORD_BOT_TOKEN in the MCP env block, then restart/reload the
client and verify that discord_health_check, discord_list_channels,
discord_get_current_bot_user, discord_get_user, discord_get_member,
discord_search_members, discord_list_roles,
discord_read_messages, discord_download_attachment, discord_search_messages,
discord_send_message, discord_edit_own_message, discord_create_thread, and
discord_add_reaction appear.
```

Expected sequence:

1. Create `.venv` in the repository root.
2. Install the package in editable mode.
3. Register the MCP server in the target client using the local executable from `.venv`.
4. Provide `DISCORD_BOT_TOKEN` in the client's `env` block.
5. Restart or reload the client.
6. Verify that the implemented Discord tools are visible.

For agent-oriented instructions, see [AGENTS.md](AGENTS.md).

## Project Quality

The repository is maintained with conventional commits, a changelog, strict type checks, and GitHub Actions CI.

CI runs automatically on:

- pull request open, reopen, update, and ready-for-review events
- pushes to `main`

CI verifies:

- package installation with development dependencies
- `pytest`
- `mypy`
- Python package build artifacts

The changelog lives in [CHANGELOG.md](CHANGELOG.md).
Security guidance lives in [SECURITY.md](SECURITY.md).
Contribution notes live in [CONTRIBUTING.md](CONTRIBUTING.md).

## Current Status

- FastMCP server entrypoint is present.
- `discord_health_check` is implemented.
- `discord_list_channels` is implemented.
- `discord_get_channel` is implemented.
- `discord_get_current_bot_user` is implemented.
- `discord_get_user` is implemented.
- `discord_get_member` is implemented with optional role resolution.
- `discord_search_members` is implemented with optional role resolution.
- `discord_list_roles` is implemented.
- `discord_read_messages` is implemented.
- `discord_download_attachment` is implemented with CDN, size, and MIME validation.
- `discord_search_messages` is implemented.
- `discord_send_message` is implemented.
- `discord_edit_own_message` is implemented.
- `discord_create_thread` is implemented.
- `discord_add_reaction` is implemented.
- Local allowlists for channels and guilds are supported.
- Optional actor attribution is supported.
- Installation snippets are included for Codex, Claude, and Cursor.

## Planned Flow

```text
Codex / Claude / Cursor
  -> calls a local MCP tool
Discord MCP Bridge
  -> validates config and policy
  -> calls Discord REST API with a bot token
Discord
  -> returns API response
```

## Local Setup

This project is designed for Python 3.11+.

With `uv`:

```bash
uv sync --dev
uv run pytest
uv run mypy
```

Without `uv`, on macOS/Linux:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python -m mypy
```

Without `uv`, on Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
.venv\Scripts\python -m mypy
```

For a runtime-only install, `pip install -e .` is enough. Use `pip install -e ".[dev]"` when you also want tests and type checks.

Before opening a pull request, run:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m mypy src tests
```

The MCP command works best after the editable install because it exposes the console script.

macOS/Linux:

```text
.venv/bin/discord-mcp-bridge
```

Windows:

```text
.venv\Scripts\discord-mcp-bridge.exe
```

## Configuration

You need a Discord bot token and a bot that has access to the target channel.

Minimum Discord permissions:

- `View Channels`
- `Read Message History` for reading messages and search
- `Send Messages` for sending messages
- `Create Public Threads` for creating public threads
- `Add Reactions` for adding reactions

The read-only user, individual member, member search, and role-listing tools do not require adding moderation permissions to the bot role. Bulk member listing is intentionally not exposed because Discord requires the privileged `GUILD_MEMBERS` intent for that endpoint.

For message bodies and rich message fields, enable the privileged `MESSAGE_CONTENT` intent for the bot in the Discord Developer Portal. Without it, Discord can return empty `content`, `attachments`, `embeds`, and `components`, and omit poll data for messages where the bot does not otherwise receive content access.

Optional but recommended local policy controls:

- `DISCORD_ALLOWED_CHANNELS`
- `DISCORD_ALLOWED_GUILDS`

```env
DISCORD_BOT_TOKEN=
DISCORD_DEFAULT_GUILD_ID=
DISCORD_ALLOWED_GUILDS=
DISCORD_ALLOWED_CHANNELS=
DISCORD_ACTOR_NAME=
DISCORD_ACTOR_DISCORD_ID=
DISCORD_APPEND_ATTRIBUTION=true
DISCORD_MAX_ATTACHMENT_BYTES=10485760
DISCORD_ALLOWED_ATTACHMENT_MIME_TYPES=
```

Minimum configuration:

```env
DISCORD_BOT_TOKEN=your-bot-token
```

Recommended configuration:

```env
DISCORD_BOT_TOKEN=your-bot-token
DISCORD_DEFAULT_GUILD_ID=your-server-id
DISCORD_ALLOWED_CHANNELS=channel-id
DISCORD_ACTOR_NAME=your-name
DISCORD_APPEND_ATTRIBUTION=true
```

Behavior notes:

- If `DISCORD_DEFAULT_GUILD_ID` is set, tools that accept an optional guild ID can use that guild deterministically.
- If `DISCORD_ALLOWED_CHANNELS` is set, channel-scoped tools only operate on listed channel IDs.
- If `DISCORD_ALLOWED_GUILDS` is set, channel-scoped tools validate the target channel's guild before acting.
- If `DISCORD_APPEND_ATTRIBUTION=true`, send and edit tools append actor attribution when `DISCORD_ACTOR_NAME` or `DISCORD_ACTOR_DISCORD_ID` is configured.
- `DISCORD_MAX_ATTACHMENT_BYTES` is the server-side attachment download ceiling; the default is 10 MiB. A tool caller can request a smaller per-call `max_bytes`, but cannot raise this ceiling.
- `DISCORD_ALLOWED_ATTACHMENT_MIME_TYPES` optionally restricts downloads with comma-separated exact MIME types or wildcards, for example `image/*,application/pdf`. When unset, any syntactically valid MIME type is accepted.

Discord setup notes:

- `DISCORD_BOT_TOKEN` comes from a Discord application bot in the Discord Developer Portal.
- Use a Discord bot token only. Do not use user tokens.
- `DISCORD_DEFAULT_GUILD_ID` is the Discord server ID.
- `DISCORD_ALLOWED_CHANNELS` is a comma-separated list of channel IDs.
- The Discord bot must be invited to the server and needs the permissions for the tools you intend to use.

## Installation Path

The most reliable local setup is:

1. Clone the repo.
2. Create `.venv`.
3. Install editable dependencies with `-e ".[dev]"`.
4. Put Discord settings in the MCP client's `env` block or in a local `.env`.
5. Point the MCP client at the console script or the module entrypoint.

Using the console script is the cleanest option after installation:

macOS/Linux:

```text
command: /path/to/repo/.venv/bin/discord-mcp-bridge
```

Windows:

```text
command: C:\Users\<you>\path\to\discord-mcp-bridge\.venv\Scripts\discord-mcp-bridge.exe
```

If a client prefers Python explicitly, this also works:

macOS/Linux:

```text
command: /path/to/repo/.venv/bin/python
args: ["-m", "discord_mcp_bridge.server"]
```

Windows:

```text
command: C:\Users\<you>\path\to\discord-mcp-bridge\.venv\Scripts\python.exe
args: ["-m", "discord_mcp_bridge.server"]
```

Do not assume this repository auto-installs itself as a marketplace plugin. It must be registered explicitly as a local MCP server.

## Codex

Add this to `~/.codex/config.toml` or your project `.codex/config.toml`:

```toml
[mcp_servers.discord-mcp-bridge]
command = "/path/to/discord-mcp-bridge/.venv/bin/discord-mcp-bridge"

[mcp_servers.discord-mcp-bridge.env]
DISCORD_BOT_TOKEN = "your-bot-token"
DISCORD_DEFAULT_GUILD_ID = "123456789012345678"
DISCORD_ALLOWED_CHANNELS = "123456789012345678"
DISCORD_ACTOR_NAME = "SouthViking"
DISCORD_APPEND_ATTRIBUTION = "true"
```

On Windows, use the `.venv\\Scripts\\discord-mcp-bridge.exe` path instead.

## Cursor

Add this to `.cursor/mcp.json` or `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "discord-mcp-bridge": {
      "command": "/path/to/discord-mcp-bridge/.venv/bin/discord-mcp-bridge",
      "args": [],
      "env": {
        "DISCORD_BOT_TOKEN": "your-bot-token",
        "DISCORD_DEFAULT_GUILD_ID": "123456789012345678",
        "DISCORD_ALLOWED_CHANNELS": "123456789012345678",
        "DISCORD_ACTOR_NAME": "SouthViking",
        "DISCORD_APPEND_ATTRIBUTION": "true"
      }
    }
  }
}
```

On Windows, use the `.venv\\Scripts\\discord-mcp-bridge.exe` path instead.

## Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "discord-mcp-bridge": {
      "command": "/path/to/discord-mcp-bridge/.venv/bin/discord-mcp-bridge",
      "args": [],
      "env": {
        "DISCORD_BOT_TOKEN": "your-bot-token",
        "DISCORD_DEFAULT_GUILD_ID": "123456789012345678",
        "DISCORD_ALLOWED_CHANNELS": "123456789012345678",
        "DISCORD_ACTOR_NAME": "SouthViking",
        "DISCORD_APPEND_ATTRIBUTION": "true"
      }
    }
  }
}
```

On Windows, use the `.venv\\Scripts\\discord-mcp-bridge.exe` path instead.

## Reloading After Changes

MCP clients usually discover tools when they start the local server process. After installing, updating this repository, adding a new tool, or changing the command path, restart or reload the MCP client. Some clients may also require a new chat/session before the refreshed tool list is visible.

## Implemented Tools

### `discord_health_check`

Inputs:

- `guild_id`: optional Discord guild/server ID.
- `channel_id`: optional Discord channel ID.
- `include_channel_sample`: whether to verify guild channel listing, default `true`.

Current behavior:

- Checks local config, token presence, guild policy, optional guild access, and optional channel access.
- Returns `status`, `guild_id`, `channel_id`, and `checks`.
- Reports degraded checks in-band instead of failing on the first diagnostic problem.

### `discord_list_channels`

Inputs:

- `guild_id`: optional Discord guild/server ID.

Current behavior:

- Lists channels visible to the bot inside the requested guild.
- Uses `DISCORD_DEFAULT_GUILD_ID` when `guild_id` is omitted.
- Returns a structured result with `status`, `guild_id`, `count`, and `channels`.
- Respects `DISCORD_ALLOWED_GUILDS`.
- Filters the returned list through `DISCORD_ALLOWED_CHANNELS` when that allowlist is configured.

### `discord_get_channel`

Inputs:

- `channel_id`: Discord channel ID.

Current behavior:

- Returns channel metadata with `id`, `name`, `guild_id`, `type`, and `position`.
- Respects `DISCORD_ALLOWED_CHANNELS` and `DISCORD_ALLOWED_GUILDS`.

### `discord_get_current_bot_user`

Inputs: none.

Current behavior:

- Returns the public Discord identity represented by the configured bot token.
- Includes `id`, `username`, `global_name`, `display_name`, avatar metadata, bot/system markers, and public flags.
- Does not require additional guild permissions.

### `discord_get_user`

Inputs:

- `user_id`: Discord user ID.

Current behavior:

- Returns public profile fields for the requested Discord user.
- Normalizes `display_name` to the global display name when present, otherwise the username.
- Does not modify the user or require moderation permissions.

### `discord_get_member`

Inputs:

- `user_id`: Discord user ID.
- `guild_id`: optional guild/server ID.
- `resolve_roles`: whether to resolve role IDs to role metadata, default `true`.

Current behavior:

- Returns the user's guild-specific member record, including nickname, display name, join timestamp, role IDs, onboarding state, timeout timestamp, voice flags, and public user profile.
- Uses `DISCORD_DEFAULT_GUILD_ID` when `guild_id` is omitted.
- Resolves member roles to names and metadata when `resolve_roles` is enabled.
- Respects `DISCORD_ALLOWED_GUILDS` and does not require moderation permissions.

### `discord_search_members`

Inputs:

- `query`: username or guild nickname prefix.
- `guild_id`: optional guild/server ID.
- `limit`: maximum number of members to return, from 1 to 100, default `25`.
- `resolve_roles`: whether to resolve role IDs to role metadata, default `true`.

Current behavior:

- Searches guild members through Discord's member search endpoint.
- Uses `DISCORD_DEFAULT_GUILD_ID` when `guild_id` is omitted.
- Returns `status`, `guild_id`, `query`, `count`, and normalized `members`.
- Respects `DISCORD_ALLOWED_GUILDS`; bulk member listing through the privileged `GUILD_MEMBERS` intent is intentionally not exposed.

### `discord_list_roles`

Inputs:

- `guild_id`: optional guild/server ID.

Current behavior:

- Lists guild roles from highest to lowest position.
- Returns role IDs, names, descriptions, colors, positions, permission bitfields, display settings, and role flags.
- Uses `DISCORD_DEFAULT_GUILD_ID` when `guild_id` is omitted.
- Respects `DISCORD_ALLOWED_GUILDS` and does not modify roles.

### `discord_read_messages`

Inputs:

- `channel_id`: Discord channel ID.
- `limit`: maximum number of matching messages to return, from 1 to 500.
- `before`: optional message ID upper bound.
- `after`: optional message ID lower bound.
- `around`: optional message ID to read around. Cannot be combined with `before` or `after`.
- `scan_limit`: optional maximum number of raw messages to scan before filtering, from 1 to 1000.
- `page_size`: optional Discord API page size, from 1 to 100.
- Optional local filters: `author_id`, `author_is_bot`, `contains`, `case_sensitive`, `has_attachments`, `has_embeds`, `pinned`, `mentions_user_id`, and `message_type`.
- Optional include flags: `include_content`, `include_attachments`, `include_embeds`, `include_stickers`, `include_poll`, `include_components`, `include_reactions`, `include_mentions`, and `include_referenced_message`.
- `oldest_first`: optionally return matched messages in chronological order instead of Discord's default newest-first order.

Current behavior:

- Reads messages visible to the configured bot in a channel.
- Uses Discord's native message cursors where possible.
- Supports local filtering after fetching messages from Discord.
- Supports controlled pagination for ranges and selective filters.
- Returns structured context including message IDs, author summaries, timestamps, content, detailed attachment metadata, rich embeds, reactions, mentions, references, and a `next_before` cursor for continuing from the last inspected message.
- Embed output includes image, thumbnail, and video metadata plus provider, author, footer, color, and fields.
- Returns sticker items, poll payloads, and message components by default. Their include flags can reduce response size when that context is not needed.
- Media entries in this response are metadata and URLs. Use `discord_download_attachment` when the MCP client needs the actual attachment bytes.
- Respects `DISCORD_ALLOWED_CHANNELS` and `DISCORD_ALLOWED_GUILDS`.

### `discord_download_attachment`

Inputs:

- `channel_id`: Discord channel ID.
- `message_id`: ID of the message that owns the attachment.
- `attachment_id`: attachment ID returned by `discord_read_messages`.
- `max_bytes`: optional per-call byte ceiling. It can lower, but never exceed, `DISCORD_MAX_ATTACHMENT_BYTES`.

Current behavior:

- Fetches the message again immediately before downloading so Discord can provide a current signed attachment URL.
- Only downloads HTTPS URLs from Discord attachment CDN hosts and paths; caller-supplied URLs are never accepted.
- Streams the response while enforcing metadata, `Content-Length`, and observed-byte limits, and rejects redirects.
- Validates Discord's declared MIME type against the CDN response and applies the optional `DISCORD_ALLOWED_ATTACHMENT_MIME_TYPES` policy.
- Uses an unauthenticated CDN client, so the bot token is never forwarded with the file request.
- Returns images and audio as native MCP image/audio blocks. Videos and other files are returned as binary embedded-resource blocks with filename, MIME type, and size metadata in the structured result.
- Respects `DISCORD_ALLOWED_CHANNELS` and `DISCORD_ALLOWED_GUILDS`.

Discord attachment URLs are signed and can expire. Agents should pass the IDs from `discord_read_messages` to this tool instead of caching and downloading an old URL themselves.

### `discord_search_messages`

Inputs:

- `contains`: required text query.
- `channel_ids`: optional list of channel IDs.
- `guild_id`: optional guild/server ID used when `channel_ids` is omitted.
- `limit`: maximum matches to return, from 1 to 100.
- `scan_limit_per_channel`: maximum raw messages to scan per channel, from 1 to 1000.
- Optional filters: `case_sensitive`, `author_id`, and `has_attachments`.
- `oldest_first`: optionally return matches in chronological order.

Current behavior:

- Searches recent visible messages by scanning channel history locally.
- When `channel_ids` is omitted, searches visible channels in the requested or default guild after allowlist filtering.
- Returns `status`, `query`, `count`, `channels_searched`, `scanned_channels`, and `messages`.
- Respects `DISCORD_ALLOWED_CHANNELS` and `DISCORD_ALLOWED_GUILDS`.

### `discord_send_message`

Inputs:

- `channel_id`: Discord channel ID.
- `content`: message content.

Current behavior:

- Sends a message to the requested channel with the configured bot token.
- Returns a structured result with `status`, `message_id`, `channel_id`, `content`, and `author_username`.
- Rejects missing config and blocked channels/guilds before sending.

### `discord_edit_own_message`

Inputs:

- `channel_id`: Discord channel ID.
- `message_id`: Discord message ID.
- `content`: replacement message content.

Current behavior:

- Edits a message through Discord's bot-token API.
- Applies the same optional actor attribution as `discord_send_message`.
- Returns `status`, `message_id`, `channel_id`, `content`, and `author_username`.
- Respects `DISCORD_ALLOWED_CHANNELS` and `DISCORD_ALLOWED_GUILDS`.

### `discord_create_thread`

Inputs:

- `channel_id`: Discord channel ID.
- `name`: thread name.
- `message_id`: optional message ID for creating a thread from a message.
- `auto_archive_duration`: auto-archive duration in minutes, from 60 to 10080, default `1440`.

Current behavior:

- Creates a public thread in a channel, or starts a thread from an existing message.
- Returns `status`, `thread_id`, `channel_id`, `name`, `parent_channel_id`, `guild_id`, and `type`.
- Respects `DISCORD_ALLOWED_CHANNELS` and `DISCORD_ALLOWED_GUILDS`.

### `discord_add_reaction`

Inputs:

- `channel_id`: Discord channel ID.
- `message_id`: Discord message ID.
- `emoji`: unicode emoji or Discord custom emoji string.

Current behavior:

- Adds a reaction to a message as the configured bot.
- URL-encodes the emoji for Discord's reaction endpoint.
- Returns `status`, `channel_id`, `message_id`, and `emoji`.
- Respects `DISCORD_ALLOWED_CHANNELS` and `DISCORD_ALLOWED_GUILDS`.

## Future Tools

- `discord_delete_own_message`
- `discord_list_thread_members`
- `discord_archive_thread`
