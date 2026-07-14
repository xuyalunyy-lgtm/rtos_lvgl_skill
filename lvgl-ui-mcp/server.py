"""Independent process entry point for the LVGL UI MCP project."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("LVGL_MCP_SERVER_NAME", "lvgl-ui-mcp")

from mcp.server import main


if __name__ == "__main__":
    raise SystemExit(main())
