"""Project-specific exceptions."""


class DiscordMcpBridgeError(Exception):
    """Base exception for Discord MCP Bridge."""


class DiscordToolNotImplementedError(DiscordMcpBridgeError):
    """Raised when a tool contract exists before its Discord API implementation."""
