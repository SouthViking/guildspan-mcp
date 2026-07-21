# AGENTS.md

This repository contains a **local MCP server** named `discord-mcp-bridge`.

If you are an AI coding agent and the user asks you to "connect", "configure", "install", or "use" this repository as a plugin/tool in an MCP-capable client, do not treat it as a marketplace plugin. Treat it as a **local MCP server project** that must be installed and then registered in the target client configuration.

## What This Repo Exposes

- MCP server name: `discord-mcp-bridge`
- Transport: local process over `stdio`
- Primary tools today: `discord_health_check`, `discord_list_channels`, `discord_get_channel`, `discord_get_current_bot_user`, `discord_get_user`, `discord_get_member`, `discord_search_members`, `discord_list_roles`, `discord_read_messages`, `discord_download_attachment`, `discord_search_messages`, `discord_send_message`, `discord_edit_own_message`, `discord_create_thread`, `discord_add_reaction`

## Required Setup

1. Create a local Python virtual environment in the repo root.

macOS/Linux:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
python -m venv .venv
```

2. Install the project in editable mode.

Runtime-only install:

macOS/Linux:

```bash
.venv/bin/python -m pip install -e .
```

Windows PowerShell:

```powershell
.venv\Scripts\python -m pip install -e .
```

Development install with tests and type checks:

macOS/Linux:

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
.venv\Scripts\python -m pip install -e ".[dev]"
```

3. Provide at least:

```env
DISCORD_BOT_TOKEN=...
```

Optional:

```env
DISCORD_ALLOWED_CHANNELS=123456789012345678
DISCORD_ALLOWED_GUILDS=123456789012345678
DISCORD_ACTOR_NAME=SouthViking
DISCORD_ACTOR_DISCORD_ID=123456789012345678
DISCORD_APPEND_ATTRIBUTION=true
DISCORD_ATTRIBUTION_TEXT=sent using Discord Bridge
DISCORD_MAX_ATTACHMENT_BYTES=10485760
DISCORD_ALLOWED_ATTACHMENT_MIME_TYPES=image/*,application/pdf
DISCORD_ALLOWED_UPLOAD_PATHS=/absolute/path/to/allowed/media
DISCORD_ALLOWED_UPLOAD_URL_HOSTS=cdn.example.com
DISCORD_MAX_UPLOAD_BYTES=10485760
DISCORD_MAX_UPLOAD_TOTAL_BYTES=25165824
DISCORD_ALLOWED_UPLOAD_MIME_TYPES=image/*,audio/*,video/*,application/pdf
```

## Preferred MCP Command

Prefer the installed console script:

macOS/Linux:

```text
/path/to/repo/.venv/bin/discord-mcp-bridge
```

Windows:

```text
C:\path\to\repo\.venv\Scripts\discord-mcp-bridge.exe
```

Fallback:

macOS/Linux:

```text
/path/to/repo/.venv/bin/python -m discord_mcp_bridge.server
```

Windows:

```text
C:\path\to\repo\.venv\Scripts\python.exe -m discord_mcp_bridge.server
```

## Prompt Users Can Give Their Agent

If a user asks how to install this from another AI client, they can say:

```text
Install this repository as a local MCP server named discord-mcp-bridge.
Do not treat it as a marketplace plugin. Create a Python virtual environment,
install the project in editable mode, register the MCP command in my client
config, set DISCORD_BOT_TOKEN in the MCP env block, then restart/reload the
client and verify that the Discord MCP tools appear.
```

## Client Registration

### Codex

Add to `~/.codex/config.toml` or project `.codex/config.toml`:

```toml
[mcp_servers.discord-mcp-bridge]
command = "/path/to/repo/.venv/bin/discord-mcp-bridge"

[mcp_servers.discord-mcp-bridge.env]
DISCORD_BOT_TOKEN = "your-bot-token"
DISCORD_ALLOWED_CHANNELS = "123456789012345678"
DISCORD_ACTOR_NAME = "SouthViking"
DISCORD_APPEND_ATTRIBUTION = "true"
DISCORD_ATTRIBUTION_TEXT = "sent using Discord Bridge"
```

On Windows, use:

```toml
command = "C:\\path\\to\\repo\\.venv\\Scripts\\discord-mcp-bridge.exe"
```

### Cursor

Add to `.cursor/mcp.json` or `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "discord-mcp-bridge": {
      "command": "/path/to/repo/.venv/bin/discord-mcp-bridge",
      "args": [],
      "env": {
        "DISCORD_BOT_TOKEN": "your-bot-token",
        "DISCORD_ALLOWED_CHANNELS": "123456789012345678",
        "DISCORD_ACTOR_NAME": "SouthViking",
        "DISCORD_APPEND_ATTRIBUTION": "true",
        "DISCORD_ATTRIBUTION_TEXT": "sent using Discord Bridge"
      }
    }
  }
}
```

On Windows, use `C:\\path\\to\\repo\\.venv\\Scripts\\discord-mcp-bridge.exe` as the command.

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "discord-mcp-bridge": {
      "command": "/path/to/repo/.venv/bin/discord-mcp-bridge",
      "args": [],
      "env": {
        "DISCORD_BOT_TOKEN": "your-bot-token",
        "DISCORD_ALLOWED_CHANNELS": "123456789012345678",
        "DISCORD_ACTOR_NAME": "SouthViking",
        "DISCORD_APPEND_ATTRIBUTION": "true",
        "DISCORD_ATTRIBUTION_TEXT": "sent using Discord Bridge"
      }
    }
  }
}
```

On Windows, use `C:\\path\\to\\repo\\.venv\\Scripts\\discord-mcp-bridge.exe` as the command.

## Verification

After registration, verify these things in order:

1. The MCP client starts the server without process errors.
2. The Discord MCP tools appear in the client's tool list.
3. A channel listing succeeds against a known guild ID.
4. An individual member lookup succeeds against a known user ID.
5. A message history read succeeds against a known channel ID.
6. An attachment download returns a native MCP media or embedded-resource block.
7. A test message succeeds against a known channel ID.
8. A media-only test succeeds using base64 or an explicitly allowed local path.
9. A combined text-and-file message returns attachment metadata.

## Reloading After Changes

MCP clients usually discover tools when they start the local server process. After installation, updates, new tools, or config path changes, restart or reload the client. Some clients may also need a new chat/session before the refreshed tool list appears.

## Important Constraints

- This repo uses a **Discord bot token**, not a user token.
- This repo is a **local MCP server**, not a hosted API.
- If no allowlists are configured, the bot can send to any channel it can access.
- The effective permissions are the intersection of:
  - Discord permissions granted to the bot
  - local allowlists configured by the installer
- Attachment downloads are limited by `DISCORD_MAX_ATTACHMENT_BYTES`, defaulting to 10 MiB.
- `DISCORD_ALLOWED_ATTACHMENT_MIME_TYPES` can optionally restrict downloads with comma-separated exact MIME types or patterns such as `image/*`.
- `discord_send_message` accepts optional `content`, up to 10 `attachments` from `path`, `url`, or `base64`, and up to 3 native `sticker_ids`.
- Local path uploads are disabled unless absolute roots are configured in `DISCORD_ALLOWED_UPLOAD_PATHS`.
- Public URL uploads reject non-HTTPS, credentialed, private/local destinations, unsafe redirects, and oversized responses. URL fetches never receive the Discord bot token.
- Outgoing files are limited by `DISCORD_MAX_UPLOAD_BYTES` per file and `DISCORD_MAX_UPLOAD_TOTAL_BYTES` per message. `DISCORD_ALLOWED_UPLOAD_MIME_TYPES` can further restrict them.
- File sending requires Discord's `ATTACH_FILES` permission. External native stickers may require `USE_EXTERNAL_STICKERS`.
- Sent and edited messages place the configured actor above the body and use `DISCORD_ATTRIBUTION_TEXT` as a footer when attribution is enabled.
