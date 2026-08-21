# Hosted authentication

GuildSpan's remote transport is a generic Streamable HTTP MCP server. It uses
the MCP OAuth 2.1 discovery flow implemented by FastMCP, with Discord as the
upstream identity provider. There is no client-specific backend behavior.

## Configuration

Apply migrations, then provide:

```env
DISCORD_BOT_TOKEN=...
DISCORD_ALLOWED_GUILDS=123456789012345678
DATABASE_URL=postgresql://user:password@host:5432/guildspan
GUILDSPAN_AUTH_ENABLED=true
GUILDSPAN_PUBLIC_BASE_URL=https://guildspan.example.com
DISCORD_OAUTH_CLIENT_ID=...
DISCORD_OAUTH_CLIENT_SECRET=...
GUILDSPAN_AUTH_SECRET=...
GUILDSPAN_HTTP_HOST=0.0.0.0
```

`GUILDSPAN_AUTH_SECRET` must contain at least 32 characters and should be
generated from a cryptographically secure random source. The Discord developer
application must contain this exact OAuth redirect URI:

```text
https://guildspan.example.com/auth/callback
```

`GUILDSPAN_PUBLIC_BASE_URL` is the origin only; do not append `/mcp`.

## Client flow

1. An MCP client connects to `https://guildspan.example.com/mcp`.
2. The unauthenticated response and protected-resource metadata advertise the
   standard OAuth authorization server.
3. The client opens a browser for GuildSpan consent and Discord login.
4. Discord authorizes the `identify` and `guilds` scopes and returns control to
   `/auth/callback`.
5. GuildSpan issues its own audience-bound access token to the MCP client. The
   upstream Discord token and the bot token are not exposed to that client.
6. Guild-scoped tools apply both operator policy and persisted user access.

Compatible clients may use dynamic client registration or client ID metadata
documents. A future GuildSpan web platform can manage grants and configuration
without changing this MCP flow.

## Guild authorization

For every guild-scoped tool call, GuildSpan requires the guild in
`DISCORD_ALLOWED_GUILDS` and confirms the authenticated user still belongs to
it. If an active persisted grant already exists, the request proceeds.

When no grant exists, GuildSpan allows a one-time bootstrap only when the user
owns the guild or has Discord's **Manage Server** permission and the service bot
can access the guild. It then records the guild installation and grants that
user access. Revoked grants remain denied unless an eligible administrator
bootstraps the guild again.

## Persistence and secrets

PostgreSQL stores users, guild installations, user grants, and OAuth provider
state. OAuth values are encrypted before storage. `GUILDSPAN_AUTH_SECRET` is
also used to sign GuildSpan's access tokens, so rotate it as a coordinated
session reset rather than as a transparent configuration change.

The local `stdio` runtime does not require OAuth or PostgreSQL and retains its
existing operator-controlled behavior.
