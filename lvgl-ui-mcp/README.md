# lvgl-ui-mcp

Independent MCP project for design-driven LVGL generation and SSIM-gated delivery.

## Ownership

This project owns:

- the MCP process entry point and server identity;
- the six public tools: `inspect_design`, `generate_ui`, `render_ui`, `compare_ui`, `refine_ui`, and `apply_patch`;
- public schemas, release versioning, and MCP-specific project tests;
- the interaction and minimal-delivery contracts.

The repository-root `mcp/` package is the compatibility engine during incremental extraction. New public entry points and MCP release configuration must be added here. Embedded workflow routing and platform constraints remain owned by the root skill.

## Run

```powershell
python lvgl-ui-mcp/server.py
python lvgl-ui-mcp/server.py --self-test
```

The server keeps internal evidence in `artifacts/lvgl_runs/<run_id>/`. Only compile-required firmware files belong in the final delivery directory.
