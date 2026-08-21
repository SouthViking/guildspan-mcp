from importlib.metadata import entry_points, version

from guildspan import __version__


def test_runtime_version_matches_distribution_metadata() -> None:
    assert __version__ == version("guildspan-mcp")


def test_console_scripts_point_to_runtime_entrypoints() -> None:
    scripts = {
        script.name: script.value
        for script in entry_points(group="console_scripts")
        if script.name.startswith("guildspan")
    }

    assert scripts == {
        "guildspan": "guildspan.local:main",
        "guildspan-http": "guildspan.app:main",
    }
