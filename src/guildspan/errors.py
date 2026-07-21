"""Project-specific exceptions."""


class GuildSpanError(Exception):
    """Base exception for GuildSpan."""


class DiscordConfigurationError(GuildSpanError):
    """Raised when required local configuration is missing or invalid."""


class DiscordPermissionError(GuildSpanError):
    """Raised when local policy blocks an attempted Discord action."""


class DiscordApiError(GuildSpanError):
    """Raised when the Discord REST API returns an error."""


class DiscordAttachmentError(GuildSpanError):
    """Raised when a Discord attachment cannot be safely downloaded."""


class DiscordUploadError(GuildSpanError):
    """Raised when an outgoing attachment cannot be safely prepared."""
