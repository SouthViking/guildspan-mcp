# Discord MCP Bridge

Discord MCP Bridge is a local MCP server that will expose Discord actions to AI coding clients such as Codex, Claude, and Cursor.

This version supports sending a message to a specific Discord channel through the official Discord REST API using a bot token.

## AI Client Quickstart

If you are connecting this repo from an AI editor or assistant, treat it as a **local MCP server project**.

Use this sequence exactly:

1. Create `.venv` in the repository root.
2. Install the package in editable mode with `.[dev]`.
3. Register the MCP server in the target client using the local executable in `.venv\Scripts\discord-mcp-bridge.exe`.
4. Provide `DISCORD_BOT_TOKEN` in the client's `env` block.
5. Restart or reload the client.
6. Verify that `discord_send_message` and `discord_list_channels` are visible as tools.

For agent-oriented instructions, see [AGENTS.md](</C:/Users/SouthViking/Desktop/discord-mcp-bridge/AGENTS.md>).

## Current Status

- FastMCP server entrypoint is present.
- `discord_list_channels` is implemented.
- `discord_send_message` is implemented.
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

Without `uv`:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
.venv\Scripts\python -m mypy
```

The MCP command works best after the editable install because it exposes the console script:

```bash
.venv\Scripts\discord-mcp-bridge
```

## Configuration

You need a Discord bot token and a bot that has access to the target channel.

Minimum Discord permissions for sending messages:

- `View Channels`
- `Send Messages`

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
```

Behavior notes:

- If `DISCORD_DEFAULT_GUILD_ID` is set, `discord_list_channels` can be called without passing a guild ID and will use that guild deterministically.
- If `DISCORD_ALLOWED_CHANNELS` is set, the tool only sends to listed channel IDs.
- If `DISCORD_ALLOWED_GUILDS` is set, the tool validates the target channel's guild before sending.
- If `DISCORD_APPEND_ATTRIBUTION=true`, the tool appends actor attribution when `DISCORD_ACTOR_NAME` or `DISCORD_ACTOR_DISCORD_ID` is configured.

## Installation Path

The most reliable local setup is:

1. Clone the repo.
2. Create `.venv`.
3. Install editable dependencies with `-e ".[dev]"`.
4. Put Discord settings in the MCP client's `env` block or in a local `.env`.
5. Point the MCP client at the console script or the module entrypoint.

Using the console script is the cleanest option after installation:

```text
command: C:\Users\<you>\path\to\discord-mcp-bridge\.venv\Scripts\discord-mcp-bridge.exe
```

If a client prefers Python explicitly, this also works:

```text
command: C:\Users\<you>\path\to\discord-mcp-bridge\.venv\Scripts\python.exe
args: ["-m", "discord_mcp_bridge.server"]
```

Do not assume this repository auto-installs itself as a marketplace plugin. It must be registered explicitly as a local MCP server.

## Codex

Add this to `~/.codex/config.toml` or your project `.codex/config.toml`:

```toml
[mcp_servers.discord-mcp-bridge]
command = "C:\\Users\\<you>\\Desktop\\discord-mcp-bridge\\.venv\\Scripts\\discord-mcp-bridge.exe"

[mcp_servers.discord-mcp-bridge.env]
DISCORD_BOT_TOKEN = "your-bot-token"
DISCORD_DEFAULT_GUILD_ID = "123456789012345678"
DISCORD_ALLOWED_CHANNELS = "123456789012345678"
DISCORD_ACTOR_NAME = "SouthViking"
DISCORD_APPEND_ATTRIBUTION = "true"
```

## Cursor

Add this to `.cursor/mcp.json` or `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "discord-mcp-bridge": {
      "command": "C:\\Users\\<you>\\Desktop\\discord-mcp-bridge\\.venv\\Scripts\\discord-mcp-bridge.exe",
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

## Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "discord-mcp-bridge": {
      "command": "C:\\Users\\<you>\\Desktop\\discord-mcp-bridge\\.venv\\Scripts\\discord-mcp-bridge.exe",
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

## Implemented Tool

### `discord_list_channels`

Inputs:

- `guild_id`: optional Discord guild/server ID.

Current behavior:

- Lists channels visible to the bot inside the requested guild.
- Uses `DISCORD_DEFAULT_GUILD_ID` when `guild_id` is omitted.
- Returns a structured result with `status`, `guild_id`, `count`, and `channels`.
- Respects `DISCORD_ALLOWED_GUILDS`.
- Filters the returned list through `DISCORD_ALLOWED_CHANNELS` when that allowlist is configured.

### `discord_send_message`

Inputs:

- `channel_id`: Discord channel ID.
- `content`: message content.

Current behavior:

- Sends a message to the requested channel with the configured bot token.
- Returns a structured result with `status`, `message_id`, `channel_id`, `content`, and `author_username`.
- Rejects missing config and blocked channels/guilds before sending.

## Future Tools

- `discord_read_messages`
- `discord_add_reaction`
- `discord_create_thread`
