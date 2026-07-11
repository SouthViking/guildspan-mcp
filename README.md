# Discord MCP Bridge

Discord MCP Bridge is a local MCP server that will expose Discord actions to AI coding clients such as Codex, Claude, and Cursor.

This first version is intentionally a scaffold. It registers the MCP server and the initial message-sending tool contract, but it does not call the Discord REST API yet.

## Current Status

- FastMCP server entrypoint is present.
- `discord_send_message` is registered as a facade tool.
- Discord REST calls are not implemented yet.
- Configuration keys are documented for the next milestone.

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

## Setup

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

## Configuration

Copy `.env.example` to `.env` when Discord REST support is implemented.

```env
DISCORD_BOT_TOKEN=
DISCORD_ALLOWED_GUILDS=
DISCORD_ALLOWED_CHANNELS=
DISCORD_ACTOR_NAME=
DISCORD_ACTOR_DISCORD_ID=
DISCORD_APPEND_ATTRIBUTION=true
```

## MCP Client Examples

From a cloned repository, configure your MCP client to run:

```json
{
  "mcpServers": {
    "discord-mcp-bridge": {
      "command": "python",
      "args": ["-m", "discord_mcp_bridge.server"],
      "env": {
        "DISCORD_BOT_TOKEN": ""
      }
    }
  }
}
```

Once packaged, the intended command will be:

```json
{
  "mcpServers": {
    "discord-mcp-bridge": {
      "command": "discord-mcp-bridge",
      "args": []
    }
  }
}
```

## Initial Tool

### `discord_send_message`

Inputs:

- `channel_id`: Discord channel ID.
- `content`: message content.

Current behavior:

- Raises a controlled `DiscordToolNotImplementedError`.

Future behavior:

- Send a message with Discord's REST API.
- Apply actor attribution when configured.
- Enforce guild/channel allowlists.

## Future Tools

- `discord_list_channels`
- `discord_read_messages`
- `discord_add_reaction`
- `discord_create_thread`
