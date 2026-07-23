import base64
from collections.abc import Sequence
from typing import Any, cast

import pytest

from guildspan.config import Settings
from guildspan.discord_client import (
    DiscordChannel,
    DiscordMessage,
    DiscordThread,
    DiscordUpload,
)
from guildspan.errors import DiscordConfigurationError, DiscordPermissionError
from guildspan.tools import _common as common_module
from guildspan.tools import messages as messages_module
from guildspan.tools.messages import (
    _discord_edit_own_message,
    _discord_send_message,
    discord_send_message,
)
from guildspan.tools.uploads import Base64Attachment


def make_settings(**kwargs: object) -> Settings:
    settings_ctor = cast(Any, Settings)
    return cast(Settings, settings_ctor(_env_file=None, **kwargs))


class FakeDiscordClient:
    def __init__(
        self,
        *,
        channel: DiscordChannel | None = None,
        message: DiscordMessage | None = None,
    ) -> None:
        self.channel = channel or DiscordChannel(
            id="1234567890",
            name="general",
            guild_id=None,
            type=0,
            position=0,
        )
        self.message = message or DiscordMessage(
            id="message-1",
            channel_id="1234567890",
            content="hello",
            author_username="guildspan-bot",
        )
        self.sent_payloads: list[tuple[str, str | None]] = []
        self.sent_attachments: list[list[DiscordUpload]] = []
        self.sent_sticker_ids: list[list[str]] = []
        self.closed = False

    async def get_channel(self, channel_id: str) -> DiscordChannel:
        return DiscordChannel(
            id=channel_id,
            name=self.channel.name,
            guild_id=self.channel.guild_id,
            type=self.channel.type,
            position=self.channel.position,
        )

    async def list_guild_channels(self, guild_id: str) -> list[DiscordChannel]:
        raise AssertionError(
            "list_guild_channels should not be called by discord_send_message"
        )

    async def list_channel_messages(
        self,
        *,
        channel_id: str,
        limit: int,
        before: str | None = None,
        after: str | None = None,
        around: str | None = None,
    ) -> list[dict[str, object]]:
        raise AssertionError(
            "list_channel_messages should not be called by discord_send_message"
        )

    async def send_message(
        self,
        *,
        channel_id: str,
        content: str | None,
        attachments: Sequence[DiscordUpload] = (),
        sticker_ids: Sequence[str] = (),
    ) -> DiscordMessage:
        self.sent_payloads.append((channel_id, content))
        self.sent_attachments.append(list(attachments))
        self.sent_sticker_ids.append(list(sticker_ids))
        returned_attachments = tuple(
            {
                "id": str(index),
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "size": len(attachment.data),
            }
            for index, attachment in enumerate(attachments)
        )
        returned_stickers = tuple(
            {"id": sticker_id, "name": f"sticker-{index}", "format_type": 1}
            for index, sticker_id in enumerate(sticker_ids)
        )
        return DiscordMessage(
            id=self.message.id,
            channel_id=channel_id,
            content=content or "",
            author_username=self.message.author_username,
            attachments=returned_attachments,
            stickers=returned_stickers,
        )

    async def edit_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> DiscordMessage:
        raise AssertionError(
            "edit_message should not be called by discord_send_message"
        )

    async def add_reaction(
        self,
        *,
        channel_id: str,
        message_id: str,
        emoji: str,
    ) -> None:
        raise AssertionError(
            "add_reaction should not be called by discord_send_message"
        )

    async def create_thread(
        self,
        *,
        channel_id: str,
        name: str,
        message_id: str | None = None,
        auto_archive_duration: int = 1440,
    ) -> DiscordThread:
        raise AssertionError(
            "create_thread should not be called by discord_send_message"
        )

    async def aclose(self) -> None:
        self.closed = True


class EditingDiscordClient(FakeDiscordClient):
    def __init__(self) -> None:
        super().__init__()
        self.edited_payloads: list[tuple[str, str, str]] = []

    async def edit_message(
        self,
        *,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> DiscordMessage:
        self.edited_payloads.append((channel_id, message_id, content))
        return DiscordMessage(
            id=message_id,
            channel_id=channel_id,
            content=content,
            author_username="guildspan-bot",
        )


@pytest.mark.asyncio
async def test_discord_send_message_rejects_missing_bot_token() -> None:
    with pytest.raises(
        DiscordConfigurationError, match="DISCORD_BOT_TOKEN is required"
    ):
        await _discord_send_message(
            channel_id="1234567890",
            content="hello",
            settings=make_settings(discord_bot_token=None),
        )


@pytest.mark.asyncio
async def test_discord_send_message_rejects_blank_channel_id() -> None:
    with pytest.raises(ValueError, match="channel_id is required"):
        await discord_send_message(channel_id=" ", content="hello")


@pytest.mark.asyncio
async def test_discord_send_message_rejects_blank_content() -> None:
    with pytest.raises(ValueError, match="At least one of content"):
        await discord_send_message(channel_id="1234567890", content=" ")


@pytest.mark.asyncio
async def test_discord_send_message_sends_message() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        content="hello",
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    assert result == {
        "status": "sent",
        "message_id": "message-1",
        "channel_id": "1234567890",
        "content": "hello\n\n-# sent using GuildSpan",
        "author_username": "guildspan-bot",
        "attachments": [],
        "stickers": [],
        "requested_locale": None,
        "resolved_locale": "en",
        "locale_fallback": False,
    }
    assert fake_client.sent_payloads == [
        ("1234567890", "hello\n\n-# sent using GuildSpan")
    ]


@pytest.mark.asyncio
async def test_discord_send_message_appends_branded_attribution() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        content="deploy done",
        locale="fr-FR",
        settings=make_settings(
            discord_bot_token="token",
            discord_actor_discord_id="4242",
            discord_append_attribution=True,
            discord_attribution_text="sent using My Bridge",
        ),
        client=fake_client,
    )

    assert result["content"] == "\n<@4242>\ndeploy done\n\n-# sent using My Bridge"
    assert fake_client.sent_payloads == [
        ("1234567890", "\n<@4242>\ndeploy done\n\n-# sent using My Bridge")
    ]


@pytest.mark.asyncio
async def test_discord_send_message_localizes_attribution_for_message_language() -> (
    None
):
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        content="Bonjour à tous !",
        locale="fr-FR",
        settings=make_settings(
            discord_bot_token="token",
            discord_actor_name="Ada",
        ),
        client=fake_client,
    )

    assert result["content"] == "\n**Ada**\nBonjour à tous !\n\n-# envoyé via GuildSpan"
    assert result["requested_locale"] == "fr-FR"
    assert result["resolved_locale"] == "fr"
    assert result["locale_fallback"] is False


@pytest.mark.asyncio
async def test_discord_send_message_falls_back_to_english_for_unknown_locale() -> None:
    result = await _discord_send_message(
        channel_id="1234567890",
        content="Ciao a tutti!",
        locale="it-IT",
        settings=make_settings(discord_bot_token="token"),
        client=FakeDiscordClient(),
    )

    assert result["content"] == "Ciao a tutti!\n\n-# sent using GuildSpan"
    assert result["requested_locale"] == "it-IT"
    assert result["resolved_locale"] == "en"
    assert result["locale_fallback"] is True


@pytest.mark.asyncio
async def test_discord_send_message_keeps_operator_attribution_override() -> None:
    result = await _discord_send_message(
        channel_id="1234567890",
        content="Bonjour",
        locale="fr",
        settings=make_settings(
            discord_bot_token="token",
            discord_attribution_text="delivered securely by My Bridge",
        ),
        client=FakeDiscordClient(),
    )

    assert result["content"] == "Bonjour\n\n-# delivered securely by My Bridge"


@pytest.mark.asyncio
async def test_discord_send_message_can_fall_back_to_actor_attribution() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        content="deploy done",
        locale="fr-FR",
        settings=make_settings(
            discord_bot_token="token",
            discord_actor_discord_id="4242",
            discord_append_attribution=True,
            discord_attribution_text=" ",
        ),
        client=fake_client,
    )

    assert result["content"] == "deploy done\n\n-# envoyé via MCP par <@4242>"


@pytest.mark.asyncio
async def test_discord_send_message_blocks_non_allowed_channel() -> None:
    fake_client = FakeDiscordClient()

    with pytest.raises(DiscordPermissionError, match="not in DISCORD_ALLOWED_CHANNELS"):
        await _discord_send_message(
            channel_id="1234567890",
            content="hello",
            settings=make_settings(
                discord_bot_token="token",
                discord_allowed_channels="9999999999",
            ),
            client=fake_client,
        )


@pytest.mark.asyncio
async def test_discord_send_message_blocks_non_allowed_guild() -> None:
    fake_client = FakeDiscordClient(
        channel=DiscordChannel(
            id="1234567890",
            name="general",
            guild_id="guild-2",
            type=0,
            position=0,
        )
    )

    with pytest.raises(DiscordPermissionError, match="not in DISCORD_ALLOWED_GUILDS"):
        await _discord_send_message(
            channel_id="1234567890",
            content="hello",
            settings=make_settings(
                discord_bot_token="token",
                discord_allowed_guilds="guild-1",
            ),
            client=fake_client,
        )


@pytest.mark.asyncio
async def test_discord_send_message_closes_managed_client() -> None:
    class RecordingDiscordClient(FakeDiscordClient):
        instances: list["RecordingDiscordClient"] = []

        def __init__(self, *, bot_token: str) -> None:
            super().__init__()
            self.bot_token = bot_token
            RecordingDiscordClient.instances.append(self)

    fake_settings = make_settings(discord_bot_token="token")
    original_factory = common_module.build_client
    original_messages_factory = cast(Any, messages_module).build_client

    try:
        common_module.build_client = lambda *, bot_token: RecordingDiscordClient(
            bot_token=bot_token
        )
        cast(Any, messages_module).build_client = common_module.build_client
        result = await _discord_send_message(
            channel_id="1234567890",
            content="hello",
            settings=fake_settings,
        )
    finally:
        common_module.build_client = original_factory
        cast(Any, messages_module).build_client = original_messages_factory

    assert result["status"] == "sent"
    assert RecordingDiscordClient.instances[0].closed is True


@pytest.mark.asyncio
async def test_discord_edit_own_message_applies_actor_attribution() -> None:
    fake_client = EditingDiscordClient()

    result = await _discord_edit_own_message(
        channel_id="1234567890",
        message_id="message-1",
        content="updated",
        settings=make_settings(
            discord_bot_token="token",
            discord_actor_name="Ada",
            discord_actor_discord_id="4242",
            discord_append_attribution=True,
            discord_attribution_text="sent using GuildSpan",
        ),
        client=fake_client,
    )

    assert result == {
        "status": "edited",
        "message_id": "message-1",
        "channel_id": "1234567890",
        "content": "\n**Ada**\nupdated\n\n-# sent using GuildSpan",
        "author_username": "guildspan-bot",
    }
    assert fake_client.edited_payloads == [
        (
            "1234567890",
            "message-1",
            "\n**Ada**\nupdated\n\n-# sent using GuildSpan",
        )
    ]


@pytest.mark.asyncio
async def test_discord_send_message_can_disable_attribution() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        content="plain message",
        settings=make_settings(
            discord_bot_token="token",
            discord_append_attribution=False,
        ),
        client=fake_client,
    )

    assert result["content"] == "plain message"


@pytest.mark.asyncio
async def test_discord_send_message_sends_attachment_without_user_text() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        locale="es-CL",
        attachments=[
            Base64Attachment(
                source_type="base64",
                data_base64=base64.b64encode(b"GIF89a").decode("ascii"),
                filename="party.gif",
                content_type="image/gif",
                description="Celebration",
                spoiler=True,
            )
        ],
        settings=make_settings(
            discord_bot_token="token",
            discord_actor_name="Ada",
        ),
        client=fake_client,
    )

    assert fake_client.sent_payloads == [
        (
            "1234567890",
            "\n**Ada**\n\n-# enviado usando GuildSpan",
        )
    ]
    assert result["resolved_locale"] == "es"
    assert fake_client.sent_attachments[0][0].filename == "SPOILER_party.gif"
    assert fake_client.sent_attachments[0][0].description == "Celebration"
    assert result["attachments"] == [
        {
            "id": "0",
            "filename": "SPOILER_party.gif",
            "content_type": "image/gif",
            "size": 6,
        }
    ]


@pytest.mark.asyncio
async def test_discord_send_message_combines_text_attachment_and_sticker() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        content="launch",
        attachments=[
            Base64Attachment(
                source_type="base64",
                data_base64=base64.b64encode(b"audio").decode("ascii"),
                filename="launch.mp3",
                content_type="audio/mpeg",
            )
        ],
        sticker_ids=["sticker-1"],
        settings=make_settings(discord_bot_token="token"),
        client=fake_client,
    )

    assert fake_client.sent_payloads == [
        ("1234567890", "launch\n\n-# sent using GuildSpan")
    ]
    assert fake_client.sent_sticker_ids == [["sticker-1"]]
    assert result["stickers"] == [
        {"id": "sticker-1", "name": "sticker-0", "format_type": 1}
    ]


@pytest.mark.asyncio
async def test_discord_send_message_sends_sticker_without_user_text() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        sticker_ids=["sticker-1"],
        settings=make_settings(
            discord_bot_token="token",
            discord_actor_name="Ada",
        ),
        client=fake_client,
    )

    assert fake_client.sent_payloads == [
        (
            "1234567890",
            "\n**Ada**\n\n-# sent using GuildSpan",
        )
    ]
    assert fake_client.sent_attachments == [[]]
    assert fake_client.sent_sticker_ids == [["sticker-1"]]
    assert result["stickers"] == [
        {"id": "sticker-1", "name": "sticker-0", "format_type": 1}
    ]


@pytest.mark.asyncio
async def test_discord_send_message_can_send_media_with_no_generated_content() -> None:
    fake_client = FakeDiscordClient()

    result = await _discord_send_message(
        channel_id="1234567890",
        attachments=[
            Base64Attachment(
                source_type="base64",
                data_base64=base64.b64encode(b"PDF").decode("ascii"),
                filename="document.pdf",
            )
        ],
        settings=make_settings(
            discord_bot_token="token",
            discord_append_attribution=False,
        ),
        client=fake_client,
    )

    assert fake_client.sent_payloads == [("1234567890", None)]
    assert result["content"] == ""


@pytest.mark.asyncio
async def test_discord_send_message_rejects_invalid_sticker_lists() -> None:
    settings = make_settings(discord_bot_token="token")
    with pytest.raises(ValueError, match="more than 3"):
        await _discord_send_message(
            channel_id="1234567890",
            sticker_ids=["1", "2", "3", "4"],
            settings=settings,
        )
    with pytest.raises(ValueError, match="duplicates"):
        await _discord_send_message(
            channel_id="1234567890",
            sticker_ids=["1", "1"],
            settings=settings,
        )
    with pytest.raises(ValueError, match=r"sticker_ids\[0\] is required"):
        await _discord_send_message(
            channel_id="1234567890",
            sticker_ids=[" "],
            settings=settings,
        )


@pytest.mark.asyncio
async def test_discord_send_message_validates_attributed_content_length() -> None:
    with pytest.raises(ValueError, match="including configured attribution"):
        await _discord_send_message(
            channel_id="1234567890",
            content="x" * 2000,
            settings=make_settings(discord_bot_token="token"),
            client=FakeDiscordClient(),
        )
