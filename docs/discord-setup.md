# Discord Bot Setup

GuildSpan uses a Discord bot token. It does not support user tokens or self-bot automation.

## 1. Create the application and bot

1. Open the [Discord Developer Portal](https://discord.com/developers/applications) and create an application.
2. Open the **Bot** page and create the bot user if Discord has not created one automatically.
3. Reset and copy the bot token. Store it only in a local `.env` file or the MCP client's environment configuration.
4. Never commit the token or paste it into issues, screenshots, logs, or chat messages.

Discord's official walkthrough is [Building your first Discord Bot](https://docs.discord.com/developers/quick-start/getting-started).

## 2. Enable message content

On the application's **Bot** page, enable **Message Content Intent** under **Privileged Gateway Intents**.

Discord also applies this intent to affected REST API responses. Without it, message `content`, `embeds`, `attachments`, and `components` can be empty and poll data can be omitted. GuildSpan does not require Presence Intent or Server Members Intent for its current tools.

Unverified apps can enable Message Content Intent directly. Verified apps may need Discord approval. See Discord's [Message Content documentation](https://docs.discord.com/developers/events/gateway#message-content-intent).

## 3. Configure installation permissions

Open the application's **Installation** page, allow installation to a server, and configure the `bot` scope. Request only the permissions needed by the tools you plan to use.

Recommended permissions for the complete current toolset:

- **View Channels**
- **Read Message History**
- **Send Messages**
- **Send Messages in Threads**
- **Attach Files**
- **Embed Links**
- **Add Reactions**
- **Create Public Threads**
- **Use External Stickers** if the bot will send stickers from outside the destination server

GuildSpan does not need Administrator, Manage Server, Manage Roles, Kick Members, Ban Members, or Manage Messages. Discord channel overrides can still deny a permission granted at the server level.

Use the generated install link to add the bot to your server. The person authorizing a server installation must have permission to manage that server. Discord documents the permission model in [OAuth2 and Permissions](https://docs.discord.com/developers/platform/oauth2-and-permissions).

## 4. Copy server and channel IDs

In Discord, enable **User Settings → Advanced → Developer Mode**. Then use the context menu on the server or channel to copy its ID.

Use the IDs to restrict GuildSpan locally:

```env
DISCORD_DEFAULT_GUILD_ID=123456789012345678
DISCORD_ALLOWED_GUILDS=123456789012345678
DISCORD_ALLOWED_CHANNELS=234567890123456789
```

Allowlists are optional, but recommended. Effective access is always the intersection of Discord permissions and these local policies.

## 5. Verify the connection

After registering GuildSpan in an MCP client, restart or reload the client and call:

1. `discord_health_check`
2. `discord_get_current_bot_user`
3. `discord_list_channels`
4. `discord_read_messages` on an allowed channel

Only after the read checks pass, send a test message to a dedicated channel.

For failures, continue with [Troubleshooting](troubleshooting.md).
