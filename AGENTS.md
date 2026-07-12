# AGENTS.md

This repository contains a **local MCP server** named `discord-mcp-bridge`.

If you are an AI coding agent and the user asks you to "connect", "configure", "install", or "use" this repository as a plugin/tool in an MCP-capable client, do not treat it as a marketplace plugin. Treat it as a **local MCP server project** that must be installed and then registered in the target client configuration.

## What This Repo Exposes

- MCP server name: `discord-mcp-bridge`
- Transport: local process over `stdio`
- Primary tools today: `discord_list_channels`, `discord_send_message`

## Required Setup

1. Create a local Python virtual environment in the repo root:

```powershell
python -m venv .venv
```

2. Install the project in editable mode:

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
```

## Preferred MCP Command

Prefer the installed console script:

```text
C:\path\to\repo\.venv\Scripts\discord-mcp-bridge.exe
```

Fallback:

```text
C:\path\to\repo\.venv\Scripts\python.exe -m discord_mcp_bridge.server
```

## Client Registration

### Codex

Add to `~/.codex/config.toml` or project `.codex/config.toml`:

```toml
[mcp_servers.discord-mcp-bridge]
command = "C:\\path\\to\\repo\\.venv\\Scripts\\discord-mcp-bridge.exe"

[mcp_servers.discord-mcp-bridge.env]
DISCORD_BOT_TOKEN = "your-bot-token"
DISCORD_ALLOWED_CHANNELS = "123456789012345678"
DISCORD_ACTOR_NAME = "SouthViking"
DISCORD_APPEND_ATTRIBUTION = "true"
```

### Cursor

Add to `.cursor/mcp.json` or `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "discord-mcp-bridge": {
      "command": "C:\\path\\to\\repo\\.venv\\Scripts\\discord-mcp-bridge.exe",
      "args": [],
      "env": {
        "DISCORD_BOT_TOKEN": "your-bot-token",
        "DISCORD_ALLOWED_CHANNELS": "123456789012345678",
        "DISCORD_ACTOR_NAME": "SouthViking",
        "DISCORD_APPEND_ATTRIBUTION": "true"
      }
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "discord-mcp-bridge": {
      "command": "C:\\path\\to\\repo\\.venv\\Scripts\\discord-mcp-bridge.exe",
      "args": [],
      "env": {
        "DISCORD_BOT_TOKEN": "your-bot-token",
        "DISCORD_ALLOWED_CHANNELS": "123456789012345678",
        "DISCORD_ACTOR_NAME": "SouthViking",
        "DISCORD_APPEND_ATTRIBUTION": "true"
      }
    }
  }
}
```

## Verification

After registration, verify these things in order:

1. The MCP client starts the server without process errors.
2. The tools `discord_list_channels` and `discord_send_message` appear in the client's tool list.
3. A channel listing succeeds against a known guild ID.
4. A test message succeeds against a known channel ID.

## Important Constraints

- This repo uses a **Discord bot token**, not a user token.
- This repo is a **local MCP server**, not a hosted API.
- If no allowlists are configured, the bot can send to any channel it can access.
- The effective permissions are the intersection of:
  - Discord permissions granted to the bot
  - local allowlists configured by the installer
