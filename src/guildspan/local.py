"""Local GuildSpan runtime over the MCP stdio transport."""

from guildspan.server import create_server


def main() -> None:
    """Run GuildSpan as a local MCP subprocess over stdio."""

    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
