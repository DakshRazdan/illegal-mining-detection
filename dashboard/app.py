"""
dashboard/app.py — Convenience runner for the FastAPI dashboard server.
OWNER: Antigravity Agent 4

The canonical ASGI app lives in src/dispatch/dashboard_api.py.
Use this file to run with uvicorn directly:

    uvicorn src.dispatch.dashboard_api:app --reload --port 5000

Or use this runner (wraps uvicorn programmatically):

    python dashboard/app.py --synthetic         # Run pipeline then serve
    python dashboard/app.py                     # Serve only
"""

from __future__ import annotations

import argparse
import sys
import uvicorn
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.logger import logger
from src.utils.config import get_env, SETTINGS
from src.dispatch.dashboard_api import app, set_pipeline_result  # noqa: F401



def main() -> None:
    parser = argparse.ArgumentParser(description="Mining Detection Dashboard Server")
    parser.add_argument("--synthetic", action="store_true",
                        help="Run synthetic pipeline before starting server")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    cfg  = SETTINGS.get("dashboard", {})
    host = args.host or get_env("FLASK_HOST", cfg.get("host", "127.0.0.1"))
    port = args.port or int(get_env("FLASK_PORT", str(cfg.get("port", 5000))))

    if args.synthetic:
        logger.info("Running synthetic pipeline before serving...")
        from scripts.demo import run_synthetic_pipeline
        from scripts.generate_dashboard import generate
        result = run_synthetic_pipeline()
        set_pipeline_result(result)
        dashboard_path = generate(result)
        logger.success("Static dashboard saved → {}", dashboard_path)

    logger.info("Starting dashboard on http://{}:{}", host, port)
    logger.info("  GET /          → Dashboard HTML or status page")
    logger.info("  GET /map       → Live Folium map")
    logger.info("  GET /api/stats → JSON stats")
    logger.info("  GET /docs      → Interactive API docs")

    uvicorn.run(
        "src.dispatch.dashboard_api:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
