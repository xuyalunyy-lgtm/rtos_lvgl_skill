"""Hard policy for separating design references from runtime UI assets."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


POLICY_ID = "design-reference-not-runtime-v1"


def assert_design_not_runtime(design_path: str | Path | None, runtime_paths: Iterable[str | Path | None]) -> None:
    """Reject a design screenshot being reused as a runtime image source.

    A design may be read for analysis, debug overlays, and visual comparison.
    It must never be copied into a generated asset directory, packed, or used
    as a page background/cutout.  Callers without a design reference pass
    ``None`` and produce an explicitly inferred layout instead.
    """
    if design_path is None:
        return
    design = Path(design_path).resolve()
    for raw_path in runtime_paths:
        if raw_path is None:
            continue
        if Path(raw_path).resolve() == design:
            raise ValueError(
                f"Design reference cannot be used as a runtime asset: {design}. "
                "Provide a separate background/cutout, or generate an inferred layout."
            )

