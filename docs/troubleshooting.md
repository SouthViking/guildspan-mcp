# Troubleshooting

Start with `discord_health_check`. It reports token, guild, channel, policy, and Discord access problems without stopping at the first degraded check.

## The GuildSpan tools do not appear

- Confirm the configured command is the absolute path to `.venv/bin/guildspan` on macOS/Linux or `.venv\Scripts\guildspan.exe` on Windows.
- Reinstall after pulling changes: `python -m pip install -e .` from the activated virtual environment.
- Restart or reload the MCP client. Some clients require a new chat or session after the tool schema changes.
- Confirm the installation with `python -m pip show guildspan-mcp`.

## The MCP process does not start

- Verify that the configured executable still exists and that the repository or virtual environment was not moved.
- If the project was moved, recreate `.venv`; virtual-environment scripts contain absolute paths.
- Confirm the client supplies `DISCORD_BOT_TOKEN` in the MCP environment block, or starts GuildSpan with the repository as its working directory when using a local `.env` file.
- Run this import-only smoke check from the repository:

  ```bash
  .venv/bin/python -c "from guildspan.server import create_server; print(create_server().name)"
  ```

## Discord returns 401 Unauthorized

The bot token is missing, invalid, expired, or was reset in the Developer Portal. Replace it in the MCP client configuration and reload the client. Never use a personal Discord user token.

## Discord returns 403 Missing Access

- Confirm the bot is installed in the target server.
- Confirm the bot can see the target channel.
- Check channel-specific permission overrides.
- Check `DISCORD_ALLOWED_GUILDS` and `DISCORD_ALLOWED_CHANNELS`; local policy can intentionally block a channel Discord would otherwise allow.

## Discord returns 403 Missing Permissions

Grant only the permission named by the error. Common mappings are:

- Reading: **View Channels** and **Read Message History**
- Sending text: **Send Messages**
- Uploading files: **Attach Files**
- Creating threads: **Create Public Threads**
- Sending inside threads: **Send Messages in Threads**
- Adding a new reaction: **Add Reactions**
- External native stickers: **Use External Stickers**

Channel overrides can deny permissions even when the bot role grants them at server level.

## Message content or media metadata is empty

Enable **Message Content Intent** on the application's Bot page in the Discord Developer Portal. Discord can otherwise return empty `content`, `embeds`, `attachments`, and `components`, and omit poll data.

After changing the intent, restart or reload the MCP client and read the message again.

## A local file upload is rejected

- `DISCORD_ALLOWED_UPLOAD_PATHS` must contain an explicit absolute root.
- The requested path must be absolute and resolve inside an allowed root.
- Directories, devices, and symlink escapes are rejected.
- Check the per-file, aggregate-size, and MIME policies.

## A URL upload is rejected

- The URL must use HTTPS and return file bytes rather than an HTML share page.
- Private, loopback, link-local, and otherwise non-public destinations are blocked.
- Every redirect is revalidated and the redirect count is limited.
- Check `DISCORD_ALLOWED_UPLOAD_URL_HOSTS`, MIME policy, and size limits.
- Put Tenor or Giphy page URLs in message `content`; use URL attachments only for direct files.

## Attachment download fails

Call `discord_read_messages` again and pass its `channel_id`, `message_id`, and `attachment_id` to `discord_download_attachment`. Discord CDN URLs are signed and can expire, so cached URLs should not be reused.

Also check `DISCORD_MAX_ATTACHMENT_BYTES` and `DISCORD_ALLOWED_ATTACHMENT_MIME_TYPES`.

## Safe diagnostic information for an issue

Include the GuildSpan version, Python version, operating system, MCP client, failing tool name, sanitized error code, and whether allowlists are enabled. Never include bot tokens, private message content, signed attachment URLs, or private server/channel IDs.
