import pytest

from guildspan.i18n import (
    get_attribution_text,
    get_legacy_actor_attribution,
    resolve_message_locale,
)


@pytest.mark.parametrize(
    ("requested", "resolved"),
    [
        ("en-US", "en"),
        ("es-CL", "es"),
        ("fr_FR", "fr"),
    ],
)
def test_resolve_message_locale_uses_supported_base_language(
    requested: str,
    resolved: str,
) -> None:
    resolution = resolve_message_locale(requested)

    assert resolution.requested == requested
    assert resolution.resolved == resolved
    assert resolution.used_fallback is False


@pytest.mark.parametrize("requested", ["de-DE", "not a locale", "x" * 100])
def test_resolve_message_locale_falls_back_for_unsupported_or_invalid_values(
    requested: str,
) -> None:
    resolution = resolve_message_locale(requested)

    assert resolution.requested == requested
    assert resolution.resolved == "en"
    assert resolution.used_fallback is True


def test_resolve_message_locale_defaults_to_english_when_omitted() -> None:
    resolution = resolve_message_locale(None)

    assert resolution.requested is None
    assert resolution.resolved == "en"
    assert resolution.used_fallback is False


def test_localized_text_comes_only_from_controlled_catalog() -> None:
    assert get_attribution_text("es") == "enviado usando GuildSpan"
    assert (
        get_legacy_actor_attribution(locale="fr", actor="Ada")
        == "envoyé via MCP par Ada"
    )
