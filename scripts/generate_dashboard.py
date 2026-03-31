"""
scripts/generate_dashboard.py — Export PipelineResult to Folium HTML.
OWNER: Antigravity Agent 4

Usage (called programmatically from demo.py):
    from scripts.generate_dashboard import generate
    path = generate(pipeline_result)

Or standalone:
    python scripts/generate_dashboard.py  (uses last saved PipelineResult)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.logger import logger
from src.types import PipelineResult


def generate(result: PipelineResult, output_dir: str = "results/demo") -> str:
    """
    Generate Folium HTML dashboard from a PipelineResult.

    Returns
    -------
    str — absolute path to the generated HTML file
    """
    from dashboard.map import build_map

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build Folium map
    fmap = build_map(result)

    # Save timestamped + latest
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ts_path     = out_dir / f"dashboard_{ts}.html"
    latest_path = out_dir / "latest.html"

    fmap.save(str(ts_path))
    fmap.save(str(latest_path))

    logger.success("Dashboard saved → {}", ts_path)
    logger.info("Latest dashboard → {}", latest_path)

    return str(ts_path)


if __name__ == "__main__":
    # Standalone: load last result from JSON if available
    result_path = Path("results/detections")
    json_files  = sorted(result_path.glob("run_*.json")) if result_path.exists() else []

    if json_files:
        logger.info("Loading latest result: {}", json_files[-1])
        # Minimal re-hydration for standalone use
        with open(json_files[-1]) as f:
            data = json.load(f)
        logger.warning("Full re-hydration not implemented — run demo.py --synthetic instead.")
    else:
        logger.info("No saved results found. Running synthetic demo...")
        from scripts.demo import run_synthetic_pipeline
        result = run_synthetic_pipeline()
        generate(result)
