from importlib.metadata import entry_points, version

from guildspan import __version__


def test_runtime_version_matches_distribution_metadata() -> None:
    assert __version__ == version("guildspan-mcp")


def test_console_script_points_to_server_entrypoint() -> None:
    scripts = entry_points(group="console_scripts", name="guildspan")

    assert len(scripts) == 1
    assert next(iter(scripts)).value == "guildspan.server:main"
