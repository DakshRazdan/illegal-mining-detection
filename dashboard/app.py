"""
dashboard/app.py — Flask server for the mining detection dashboard.
OWNER: Antigravity Agent 4

Usage:
    python dashboard/app.py                     # Start server (uses latest result)
    python dashboard/app.py --synthetic         # Run pipeline first, then serve

Endpoints:
    GET /              → Serve latest dashboard HTML
    GET /map           → Live Folium map (server-side render)
    GET /api/*         → JSON API (from dashboard_api.py Blueprint)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask, send_file, redirect, url_for
from flask_cors import CORS

from src.utils.logger import logger
from src.utils.config import get_env, SETTINGS
from src.dispatch.dashboard_api import api as api_blueprint, set_pipeline_result


def create_app() -> Flask:
    """Application factory."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    CORS(app)

    # Register API blueprint at /api/
    app.register_blueprint(api_blueprint)

    # ---------------------------------------------------------------------------
    # Routes
    # ---------------------------------------------------------------------------

    @app.route("/")
    def index():
        """Serve the latest generated dashboard HTML."""
        latest = Path("results/demo/latest.html")
        if latest.exists():
            return send_file(str(latest.resolve()))
        return redirect(url_for("live_map"))

    @app.route("/map")
    def live_map():
        """Render a live Folium map server-side from current pipeline result."""
        from src.dispatch.dashboard_api import get_pipeline_result
        result = get_pipeline_result()

        if result is None:
            return (
                "<html><body style='background:#0a0f1a;color:#fff;font-family:Inter,sans-serif;"
                "display:flex;align-items:center;justify-content:center;height:100vh;margin:0'>"
                "<div style='text-align:center'>"
                "<div style='font-size:24px;color:#FF9933'>🛰 Mining Watch</div>"
                "<div style='margin-top:12px;color:rgba(255,255,255,0.6)'>"
                "No pipeline result loaded.<br/>"
                "Run: <code style='background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px'>"
                "python scripts/demo.py --synthetic</code></div></div></body></html>"
            ), 503

        from dashboard.map import build_map
        fmap = build_map(result)
        return fmap._repr_html_()

    @app.route("/api/map-html")
    def map_html():
        """Return Folium map as HTML fragment (for embedding)."""
        from src.dispatch.dashboard_api import get_pipeline_result
        result = get_pipeline_result()
        if not result:
            return "", 204
        from dashboard.map import build_map
        return build_map(result)._repr_html_()

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Mining Detection Dashboard Server")
    parser.add_argument("--synthetic", action="store_true",
                        help="Run synthetic pipeline before starting server")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    cfg = SETTINGS.get("dashboard", {})
    host = args.host or get_env("FLASK_HOST", cfg.get("host", "0.0.0.0"))
    port = args.port or int(get_env("FLASK_PORT", str(cfg.get("port", 5000))))
    debug = get_env("FLASK_DEBUG", "false").lower() == "true"

    app = create_app()

    if args.synthetic:
        logger.info("Running synthetic pipeline before serving...")
        from scripts.demo import run_synthetic_pipeline
        result = run_synthetic_pipeline()
        set_pipeline_result(result)

        # Also generate static HTML
        from scripts.generate_dashboard import generate
        dashboard_path = generate(result)
        logger.success("Static dashboard saved → {}", dashboard_path)

    logger.info("Starting Flask dashboard on http://{}:{}", host, port)
    logger.info("  GET /          → Latest dashboard HTML")
    logger.info("  GET /map       → Live Folium map")
    logger.info("  GET /api/stats → JSON stats")

    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
