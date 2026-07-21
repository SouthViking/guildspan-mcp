"""Project-specific exceptions."""


class DiscordMcpBridgeError(Exception):
    """Base exception for Discord MCP Bridge."""


class DiscordConfigurationError(DiscordMcpBridgeError):
    """Raised when required local configuration is missing or invalid."""


class DiscordPermissionError(DiscordMcpBridgeError):
    """Raised when local policy blocks an attempted Discord action."""


class DiscordApiError(DiscordMcpBridgeError):
    """Raised when the Discord REST API returns an error."""


class DiscordAttachmentError(DiscordMcpBridgeError):
    """Raised when a Discord attachment cannot be safely downloaded."""


class DiscordUploadError(DiscordMcpBridgeError):
    """Raised when an outgoing attachment cannot be safely prepared."""
