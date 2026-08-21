"""FastMCP server construction and tool registration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider
from fastmcp.server.server import LifespanCallable
from mcp.types import ToolAnnotations

from guildspan import __version__
from guildspan.tools.attachments import discord_download_attachment
from guildspan.tools.channels import discord_get_channel, discord_list_channels
from guildspan.tools.diagnostics import discord_health_check
from guildspan.tools.history import discord_read_messages
from guildspan.tools.messages import discord_edit_own_message, discord_send_message
from guildspan.tools.people import (
    discord_get_current_bot_user,
    discord_get_member,
    discord_get_user,
    discord_list_roles,
    discord_search_members,
)
from guildspan.tools.reactions import discord_add_reaction
from guildspan.tools.search import discord_search_messages
from guildspan.tools.threads import discord_create_thread

GUILDSPAN_WEBSITE_URL = "https://github.com/SouthViking/guildspan-mcp"
GUILDSPAN_INSTRUCTIONS = (
    "GuildSpan gives authorized users read and write access to Discord through a "
    "centrally configured bot. Resolve guild, channel, user, and message IDs with "
    "read-only tools; never guess IDs. Treat sends, edits, thread creation, and "
    "reactions as external side effects and perform only the exact actions the user "
    "requested. Do not automatically retry a write after an ambiguous timeout. "
    "Discord permissions and GuildSpan authorization are enforced server-side. "
    "Never request bot or OAuth tokens through tool arguments."
)


@dataclass(frozen=True)
class ToolRegistration:
    """User-facing metadata and safety behavior for one MCP tool."""

    handler: Callable[..., Any]
    title: str
    description: str
    annotations: ToolAnnotations


READ_ONLY_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
EXTERNAL_WRITE_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)
EXTERNAL_IDEMPOTENT_WRITE_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
EXTERNAL_DESTRUCTIVE_WRITE_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=True,
)
EXTERNAL_DESTRUCTIVE_IDEMPOTENT_WRITE_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=True,
)

TOOL_REGISTRATIONS = (
    ToolRegistration(
        handler=discord_health_check,
        title="Check Discord connection",
        description=(
            "Use this to diagnose GuildSpan configuration, authorization, and basic "
            "Discord API access. It only reads status and optional guild or channel "
            "metadata; it does not change Discord."
        ),
        annotations=READ_ONLY_TOOL,
    ),
    ToolRegistration(
        handler=discord_list_channels,
        title="List Discord channels",
        description=(
            "Use this to discover channel IDs and metadata in an authorized Discord "
            "server. It returns only channels visible to the configured bot and does "
            "not change Discord."
        ),
        annotations=READ_ONLY_TOOL,
    ),
    ToolRegistration(
        handler=discord_get_channel,
        title="Get Discord channel",
        description=(
            "Use this to verify one Discord channel ID and retrieve its visible "
            "metadata before reading from or writing to it. It does not change Discord."
        ),
        annotations=READ_ONLY_TOOL,
    ),
    ToolRegistration(
        handler=discord_get_current_bot_user,
        title="Get GuildSpan bot identity",
        description=(
            "Use this to inspect the Discord identity represented by the configured "
            "GuildSpan bot token. It does not change Discord."
        ),
        annotations=READ_ONLY_TOOL,
    ),
    ToolRegistration(
        handler=discord_get_user,
        title="Get Discord user",
        description=(
            "Use this when a Discord user ID is known and public profile fields are "
            "needed. This lookup does not verify guild membership and does not change "
            "Discord."
        ),
        annotations=READ_ONLY_TOOL,
    ),
    ToolRegistration(
        handler=discord_get_member,
        title="Get Discord server member",
        description=(
            "Use this to retrieve an authorized server member and optionally resolve "
            "their role IDs to role metadata. It does not change the member or Discord."
        ),
        annotations=READ_ONLY_TOOL,
    ),
    ToolRegistration(
        handler=discord_search_members,
        title="Search Discord server members",
        description=(
            "Use this to find members of an authorized Discord server by username or "
            "nickname prefix and optionally resolve their roles. It does not change "
            "Discord."
        ),
        annotations=READ_ONLY_TOOL,
    ),
    ToolRegistration(
        handler=discord_list_roles,
        title="List Discord server roles",
        description=(
            "Use this to inspect roles and permissions in an authorized Discord server. "
            "It does not create, edit, assign, or delete roles."
        ),
        annotations=READ_ONLY_TOOL,
    ),
    ToolRegistration(
        handler=discord_read_messages,
        title="Read Discord messages",
        description=(
            "Use this to read, filter, or page through messages visible to the bot in "
            "one authorized Discord channel. It does not change messages or Discord."
        ),
        annotations=READ_ONLY_TOOL,
    ),
    ToolRegistration(
        handler=discord_download_attachment,
        title="Download Discord attachment",
        description=(
            "Use this with channel, message, and attachment IDs returned by message "
            "tools to retrieve one bounded Discord-hosted attachment. It reads content "
            "without modifying the message or attachment."
        ),
        annotations=READ_ONLY_TOOL,
    ),
    ToolRegistration(
        handler=discord_search_messages,
        title="Search Discord messages",
        description=(
            "Use this to search recent visible message history across specified channels "
            "or an authorized server. It scans existing content and does not change "
            "Discord."
        ),
        annotations=READ_ONLY_TOOL,
    ),
    ToolRegistration(
        handler=discord_send_message,
        title="Send Discord message",
        description=(
            "Use this only when the user wants to send content to a specific Discord "
            "channel. It creates an externally visible message and may include text, "
            "attachments, or stickers; repeated calls create additional messages."
        ),
        annotations=EXTERNAL_DESTRUCTIVE_WRITE_TOOL,
    ),
    ToolRegistration(
        handler=discord_edit_own_message,
        title="Edit GuildSpan message",
        description=(
            "Use this only when the user wants to replace the content of a specific "
            "message previously sent by the configured bot. It overwrites externally "
            "visible message content and cannot edit another author's message."
        ),
        annotations=EXTERNAL_DESTRUCTIVE_IDEMPOTENT_WRITE_TOOL,
    ),
    ToolRegistration(
        handler=discord_create_thread,
        title="Create Discord thread",
        description=(
            "Use this only when the user wants a new public Discord thread in a "
            "specific channel or from a specific message. It creates externally visible "
            "Discord state; repeated calls can create duplicate threads."
        ),
        annotations=EXTERNAL_WRITE_TOOL,
    ),
    ToolRegistration(
        handler=discord_add_reaction,
        title="Add Discord reaction",
        description=(
            "Use this only when the user wants the GuildSpan bot to add a specific "
            "emoji reaction to a specific Discord message. It changes externally "
            "visible Discord state; repeating the same call has no additional effect."
        ),
        annotations=EXTERNAL_IDEMPOTENT_WRITE_TOOL,
    ),
)


def create_server(
    *,
    auth: AuthProvider | None = None,
    lifespan: LifespanCallable[dict[str, Any]] | None = None,
) -> FastMCP:
    """Create and configure the GuildSpan server."""

    mcp = FastMCP(
        "GuildSpan",
        instructions=GUILDSPAN_INSTRUCTIONS,
        version=__version__,
        website_url=GUILDSPAN_WEBSITE_URL,
        auth=auth,
        lifespan=lifespan,
    )
    for registration in TOOL_REGISTRATIONS:
        mcp.tool(
            registration.handler,
            title=registration.title,
            description=registration.description,
            annotations=registration.annotations,
        )
    return mcp


def main() -> None:
    """Run the legacy local entrypoint over stdio.

    New integrations should use :mod:`guildspan.local`. This wrapper keeps
    ``python -m guildspan.server`` compatible with earlier releases.
    """

    from guildspan.local import main as run_local

    run_local()


if __name__ == "__main__":
    main()
