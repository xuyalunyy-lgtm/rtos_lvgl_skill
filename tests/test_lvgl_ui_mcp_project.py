import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_root_routes_lvgl_server_through_independent_project() -> None:
    config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["lvgl-ui-mcp"]
    assert server["args"] == ["lvgl-ui-mcp/server.py"]
    assert "freertos-embedded-architect" not in config["mcpServers"]


def test_project_has_its_own_metadata_entrypoint_and_mcp_config() -> None:
    project = ROOT / "lvgl-ui-mcp"
    assert (project / "pyproject.toml").is_file()
    assert (project / "server.py").is_file()
    config = json.loads((project / ".mcp.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["lvgl-ui-mcp"]
    assert server["args"] == ["server.py"]
    assert server["env"]["LVGL_MCP_SERVER_VERSION"] == "0.1.0"
