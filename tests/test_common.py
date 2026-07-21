import pytest

from guildspan.tools._common import optional_id, required_text


def test_optional_id_treats_blank_text_as_missing() -> None:
    assert optional_id("   ") is None


def test_required_text_rejects_blank_text() -> None:
    with pytest.raises(ValueError, match="emoji is required"):
        required_text("   ", "emoji")
