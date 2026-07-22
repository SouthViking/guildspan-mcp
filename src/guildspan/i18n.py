"""Controlled localization for GuildSpan-generated message text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

DEFAULT_LOCALE: Final = "en"

ATTRIBUTION_TEXTS: Final = {
    "en": "sent using GuildSpan",
    "es": "enviado usando GuildSpan",
    "fr": "envoyé via GuildSpan",
}

LEGACY_ACTOR_ATTRIBUTION_TEMPLATES: Final = {
    "en": "sent via MCP by {actor}",
    "es": "enviado vía MCP por {actor}",
    "fr": "envoyé via MCP par {actor}",
}

SUPPORTED_LOCALES: Final = tuple(sorted(ATTRIBUTION_TEXTS))

_LOCALE_RE = re.compile(r"^[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{1,8})*$")


@dataclass(frozen=True, slots=True)
class LocaleResolution:
    """A caller-provided locale resolved against GuildSpan's catalog."""

    requested: str | None
    resolved: str
    used_fallback: bool


def resolve_message_locale(locale: str | None) -> LocaleResolution:
    """Resolve a message locale, falling back safely to English."""

    requested = locale.strip() if locale is not None else None
    if not requested:
        return LocaleResolution(
            requested=None,
            resolved=DEFAULT_LOCALE,
            used_fallback=False,
        )

    if _LOCALE_RE.fullmatch(requested) is None:
        return LocaleResolution(
            requested=requested,
            resolved=DEFAULT_LOCALE,
            used_fallback=True,
        )

    language = requested.replace("_", "-").partition("-")[0].lower()
    if language in ATTRIBUTION_TEXTS:
        return LocaleResolution(
            requested=requested,
            resolved=language,
            used_fallback=False,
        )

    return LocaleResolution(
        requested=requested,
        resolved=DEFAULT_LOCALE,
        used_fallback=True,
    )


def get_attribution_text(locale: str) -> str:
    """Return the controlled branded attribution for a resolved locale."""

    return ATTRIBUTION_TEXTS[locale]


def get_legacy_actor_attribution(*, locale: str, actor: str) -> str:
    """Return the controlled actor attribution for a resolved locale."""

    return LEGACY_ACTOR_ATTRIBUTION_TEMPLATES[locale].format(actor=actor)
