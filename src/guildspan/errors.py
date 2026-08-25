"""Project-specific exceptions."""


class GuildSpanError(Exception):
    """Base exception for GuildSpan."""


class DiscordConfigurationError(GuildSpanError):
    """Raised when required local configuration is missing or invalid."""


class DiscordPermissionError(GuildSpanError):
    """Raised when local policy blocks an attempted Discord action."""


class DiscordApiError(GuildSpanError):
    """Raised when the Discord REST API returns an error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class DiscordAttachmentError(GuildSpanError):
    """Raised when a Discord attachment cannot be safely downloaded."""


class DiscordUploadError(GuildSpanError):
    """Raised when an outgoing attachment cannot be safely prepared."""
