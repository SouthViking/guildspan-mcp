# Discord MCP Bridge

Discord MCP Bridge is a local MCP server that will expose Discord actions to AI coding clients such as Codex, Claude, and Cursor.

This version supports listing Discord channels and sending messages through the official Discord REST API using a bot token.

It is not a hosted service or marketplace plugin. It is a local MCP server that runs on the user's machine and is registered in an MCP-capable client.

## AI Client Quickstart

If you are connecting this repo from an AI editor or assistant, treat it as a **local MCP server project**.

You can give an AI coding agent this prompt:

```text
Install this repository as a local MCP server named discord-mcp-bridge.
Do not treat it as a marketplace plugin. Create a Python virtual environment,
install the project in editable mode, register the MCP command in my client
config, set DISCORD_BOT_TOKEN in the MCP env block, then restart/reload the
client and verify that discord_list_channels and discord_send_message appear.
```

Expected sequence:

1. Create `.venv` in the repository root.
2. Install the package in editable mode.
3. Register the MCP server in the target client using the local executable from `.venv`.
4. Provide `DISCORD_BOT_TOKEN` in the client's `env` block.
5. Restart or reload the client.
6. Verify that `discord_send_message` and `discord_list_channels` are visible as tools.

For agent-oriented instructions, see [AGENTS.md](AGENTS.md).

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

- If `DISCORD_DEFAULT_GUILD_ID` is set, `discord_list_channels` can be called without passing a guild ID and will use that guild deterministically.
- If `DISCORD_ALLOWED_CHANNELS` is set, the tool only sends to listed channel IDs.
- If `DISCORD_ALLOWED_GUILDS` is set, the tool validates the target channel's guild before sending.
- If `DISCORD_APPEND_ATTRIBUTION=true`, the tool appends actor attribution when `DISCORD_ACTOR_NAME` or `DISCORD_ACTOR_DISCORD_ID` is configured.

Discord setup notes:

- `DISCORD_BOT_TOKEN` comes from a Discord application bot in the Discord Developer Portal.
- `DISCORD_DEFAULT_GUILD_ID` is the Discord server ID.
- `DISCORD_ALLOWED_CHANNELS` is a comma-separated list of channel IDs.
- The Discord bot must be invited to the server and needs at least `View Channels` and `Send Messages`.

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
