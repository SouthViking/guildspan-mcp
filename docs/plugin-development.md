# GuildSpan plugin development

The distributable GuildSpan plugin lives in `plugins/guildspan`. It connects
Codex and ChatGPT to the generic hosted MCP endpoint; the backend remains
client-independent.

## Package layout

```text
plugins/guildspan/
├── .app.json
├── .codex-plugin/plugin.json
├── .mcp.json
├── assets/
└── skills/guildspan-discord/
```

`.app.json` references the GuildSpan app registered in ChatGPT developer mode.
This makes the packaged plugin reuse the same OpenAI app identity instead of
creating a second connector during installation.

`.mcp.json` points to the production Streamable HTTP endpoint at
`https://guildspan-mcp-production.up.railway.app/mcp`. Authentication is
discovered through the MCP OAuth 2.1 metadata already exposed by GuildSpan. It
also keeps the remote MCP available directly to Codex clients that load MCP
servers from the plugin package.

## Validate

From the repository root:

```bash
python3 <plugin-creator-root>/scripts/validate_plugin.py plugins/guildspan
python3 <skill-creator-root>/scripts/quick_validate.py plugins/guildspan/skills/guildspan-discord
```

`plugin-creator-root` and `skill-creator-root` are the installation directories
of the corresponding Codex skills. In a standard personal installation, they
live below `$CODEX_HOME/skills/.system`.

The local catalog for development is `.agents/plugins/marketplace.json` and is
named `guildspan-local`. Add the repository as a local marketplace once, then
install the plugin:

```bash
codex plugin marketplace add "$PWD"
codex plugin add guildspan@guildspan-local
```

After changing the installed plugin, update its cachebuster with the bundled
plugin-creator helper, reinstall it, and start a new task so Codex reloads the
skills and MCP configuration.

## Release boundary

The repository marketplace is for development and testing. The registered app
is currently private and in development mode. Public publication still requires
verified publisher identity, production support and legal URLs, review fixtures,
and OpenAI review.
