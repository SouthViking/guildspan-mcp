"""Hosted GuildSpan HTTP application."""

from __future__ import annotations

from typing import cast

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from guildspan import __version__
from guildspan.config import load_settings
from guildspan.server import create_server


async def health_check(_request: Request) -> JSONResponse:
    """Return a dependency-free liveness response."""

    return JSONResponse(
        {
            "status": "ok",
            "service": "guildspan",
            "version": __version__,
        }
    )


def create_http_app() -> Starlette:
    """Create the Streamable HTTP MCP application."""

    app = create_server().http_app(
        path="/mcp",
        stateless_http=True,
        transport="streamable-http",
    )
    app.router.routes.insert(
        0,
        Route("/health", endpoint=health_check, methods=["GET"]),
    )
    return cast(Starlette, app)


app = create_http_app()


def main() -> None:
    """Run the hosted HTTP application with Uvicorn."""

    settings = load_settings()
    uvicorn.run(
        app,
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.http_log_level,
    )


if __name__ == "__main__":
    main()
