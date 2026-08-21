import httpx
import pytest
import uvicorn

from guildspan import __version__
from guildspan import app as app_module
from guildspan.app import create_http_app
from guildspan.config import Settings


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
