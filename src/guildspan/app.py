"""Hosted GuildSpan HTTP application."""

from __future__ import annotations

from typing import cast

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from guildspan import __version__
from guildspan.config import Settings, load_settings
from guildspan.hosted import HostedRuntime, create_hosted_runtime
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


def create_http_app(
    settings: Settings | None = None,
    *,
    hosted_runtime: HostedRuntime | None = None,
) -> Starlette:
    """Create the Streamable HTTP MCP application."""

    resolved_settings = settings or load_settings()
    if resolved_settings.auth_enabled:
        runtime = hosted_runtime or create_hosted_runtime(resolved_settings)
        server = create_server(auth=runtime.auth, lifespan=runtime.lifespan)
    else:
        if resolved_settings.http_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(
                "Unauthenticated HTTP is restricted to a loopback host. Set "
                "GUILDSPAN_AUTH_ENABLED=true before binding publicly."
            )
        server = create_server()

    app = server.http_app(
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
