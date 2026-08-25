from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "guildspan"
MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
APP_PATH = PLUGIN_ROOT / ".app.json"
MCP_PATH = PLUGIN_ROOT / ".mcp.json"
PRODUCTION_MCP_URL = "https://guildspan-mcp-production.up.railway.app/mcp"
REGISTERED_APP_ID = "plugin_asdk_app_6a8cc064f71c8191bd350e8265239463"


def test_plugin_manifest_references_existing_components() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["name"] == "guildspan"
    assert manifest["apps"] == "./.app.json"
    assert manifest["mcpServers"] == "./.mcp.json"
    assert manifest["skills"] == "./skills/"
    assert manifest["interface"]["displayName"] == "GuildSpan"
    assert manifest["interface"]["category"] == "Communication"

    for field in ("composerIcon", "logo"):
        relative_path = manifest["interface"][field].removeprefix("./")
        assert (PLUGIN_ROOT / relative_path).is_file()


def test_plugin_references_registered_openai_app() -> None:
    config = json.loads(APP_PATH.read_text(encoding="utf-8"))

    assert config == {
        "apps": {
            "guildspan": {
                "id": REGISTERED_APP_ID,
            }
        }
    }


def test_plugin_uses_production_oauth_mcp_endpoint() -> None:
    config = json.loads(MCP_PATH.read_text(encoding="utf-8"))
    server = config["mcpServers"]["guildspan"]

    assert server == {
        "type": "http",
        "url": PRODUCTION_MCP_URL,
        "oauth_resource": PRODUCTION_MCP_URL,
    }


def test_plugin_skill_has_no_scaffold_placeholders() -> None:
    skill = (PLUGIN_ROOT / "skills" / "guildspan-discord" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "[TODO:" not in skill
    assert "Discord bot tokens" in skill
    assert "discord_list_guilds" in skill
