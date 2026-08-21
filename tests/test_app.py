import httpx
import pytest
import uvicorn
from key_value.aio.stores.memory import MemoryStore

from guildspan import __version__
from guildspan import app as app_module
from guildspan.app import create_http_app
from guildspan.config import Settings
from guildspan.hosted import create_hosted_runtime, normalize_asyncpg_url
from guildspan.persistence import Database


@pytest.mark.asyncio
async def test_health_check_returns_service_metadata() -> None:
    transport = httpx.ASGITransport(app=create_http_app())
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "guildspan",
        "version": __version__,
    }


def test_http_app_exposes_streamable_mcp_route() -> None:
    app = create_http_app()

    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


def test_unauthenticated_http_cannot_bind_publicly() -> None:
    settings = Settings.model_validate({"GUILDSPAN_HTTP_HOST": "0.0.0.0"})

    with pytest.raises(ValueError, match="GUILDSPAN_AUTH_ENABLED=true"):
        create_http_app(settings)


def test_asyncpg_url_normalization_accepts_railway_and_sqlalchemy_urls() -> None:
    assert normalize_asyncpg_url("postgres://user:pass@db/guildspan") == (
        "postgresql://user:pass@db/guildspan"
    )
    assert normalize_asyncpg_url("postgresql+psycopg://user:pass@db/guildspan") == (
        "postgresql://user:pass@db/guildspan"
    )
    assert normalize_asyncpg_url("postgresql+asyncpg://user:pass@db/guildspan") == (
        "postgresql://user:pass@db/guildspan"
    )


@pytest.mark.asyncio
async def test_authenticated_http_exposes_oauth_and_protects_mcp() -> None:
    settings = Settings.model_validate(
        {
            "discord_bot_token": "bot-token",
            "discord_allowed_guilds": "guild-1",
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "GUILDSPAN_AUTH_ENABLED": True,
            "GUILDSPAN_PUBLIC_BASE_URL": "https://guildspan.example.com",
            "DISCORD_OAUTH_CLIENT_ID": "discord-app",
            "DISCORD_OAUTH_CLIENT_SECRET": "oauth-secret",
            "GUILDSPAN_AUTH_SECRET": "x" * 32,
        }
    )
    database = Database(settings.require_database_url())
    oauth_http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(500, json={"message": "unexpected"})
        )
    )
    runtime = create_hosted_runtime(
        settings,
        client_storage=MemoryStore(),
        database=database,
        http_client=oauth_http_client,
    )
    app = create_http_app(settings, hosted_runtime=runtime)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            metadata_response = await client.get(
                "/.well-known/oauth-protected-resource/mcp"
            )
            mcp_response = await client.post(
                "/mcp",
                headers={
                    "accept": "application/json, text/event-stream",
                    "content-type": "application/json",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "generic-client", "version": "1"},
                    },
                },
            )

    assert metadata_response.status_code == 200
    metadata = metadata_response.json()
    assert metadata["resource"] == "https://guildspan.example.com/mcp"
    assert metadata["authorization_servers"] == ["https://guildspan.example.com/"]
    assert mcp_response.status_code == 401
    assert "Bearer" in mcp_response.headers["www-authenticate"]


def test_http_main_runs_uvicorn_with_runtime_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings.model_validate(
        {
            "GUILDSPAN_HTTP_HOST": "0.0.0.0",
            "PORT": 9000,
            "GUILDSPAN_HTTP_LOG_LEVEL": "debug",
        }
    )
    calls: list[dict[str, object]] = []

    def record_run(
        application: object,
        *,
        host: str,
        port: int,
        log_level: str,
    ) -> None:
        calls.append(
            {
                "application": application,
                "host": host,
                "port": port,
                "log_level": log_level,
            }
        )

    monkeypatch.setattr(app_module, "load_settings", lambda: settings)
    monkeypatch.setattr(uvicorn, "run", record_run)

    app_module.main()

    assert calls == [
        {
            "application": app_module.app,
            "host": "0.0.0.0",
            "port": 9000,
            "log_level": "debug",
        }
    ]
