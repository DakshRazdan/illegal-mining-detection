"""
src/dispatch/mining_endpoints.py — FastAPI router for mining data endpoints.
OWNER: Antigravity Agent 3

Mounts under /api/mining in dashboard_api.py.

Endpoints:
    GET  /api/mining/map                              → GeoJSON hotspots + stats
    GET  /api/mining/overlay/{aoi}/{index}            → PNG base64 index overlay
    GET  /api/mining/stats                            → Temporal timeline + summary
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from src.dispatch.colab_bridge import (
    get_hotspot_geojson,
    get_mining_stats_timeline,
    get_temporal_frame,
    get_temporal_periods,
    is_loaded,
    render_index_png,
)
from src.utils.logger import logger

router = APIRouter()


# ── /api/mining/map ────────────────────────────────────────────────────────

@router.get("/map")
async def mining_map():
    """
    Return GeoJSON FeatureCollection of mining hotspots derived from the
    ingested Colab mining_score array.

    script.js calls this in loadRealHotspots() and loadReportsData().
    Response shape:
        {
            geojson: { type, features: [...], stats: {...} },
            stats:   { high_risk_pct, n_hotspots, ... }
        }
    """
    geojson = get_hotspot_geojson(threshold=0.55)
    stats   = geojson.pop("stats", {})

    return {
        "geojson": geojson,
        "stats":   stats,
        "source":  "colab_ingest" if is_loaded() else "synthetic",
    }


# ── /api/mining/overlay/{aoi}/{index} ─────────────────────────────────────

@router.get("/overlay/{aoi}/{index_name}")
async def mining_overlay(
    aoi:        str,
    index_name: str,
    period_idx: int = Query(default=11, ge=0, le=11),
):
    """
    Return a PNG base64 raster overlay for the given spectral index + time period.

    Called by script.js:
        switchIndex()        — on tab click
        slider input event   — on time slider drag

    index_name values: ndvi | bsi | ndwi | turbidity | mining

    Response:
        { png_b64: "...", source: "sentinel2"|"synthetic", label: "..." }
    """
    valid_indices = {"ndvi", "bsi", "ndwi", "turbidity", "mining"}
    if index_name not in valid_indices:
        return JSONResponse(
            {"error": f"Unknown index '{index_name}'. Valid: {sorted(valid_indices)}"},
            status_code=400,
        )

    png = render_index_png(index_name, period_idx=period_idx)

    if not png:
        # No Colab data loaded — return empty/synthetic response so JS
        # gracefully falls back to its existing temporal/frame endpoint
        return {
            "png_b64": None,
            "source":  "synthetic",
            "label":   index_name.upper(),
            "aoi":     aoi,
            "period_idx": period_idx,
        }

    source = "sentinel2" if is_loaded() else "synthetic"
    logger.debug("Overlay rendered: aoi=%s index=%s period=%d source=%s",
                 aoi, index_name, period_idx, source)

    return {
        "png_b64": png,
        "source":  source,
        "label":   index_name.upper(),
        "aoi":     aoi,
        "period_idx": period_idx,
    }


# ── /api/mining/stats ─────────────────────────────────────────────────────

@router.get("/stats")
async def mining_stats():
    """
    Return temporal timeline + summary used by the right-sidebar charts.

    script.js calls this in refreshData() to update:
        - veg-chart (NDVI trend line)
        - AI accuracy bar
        - ai-accuracy / ai-realtime KPI values
        - model-tag label

    Response shape:
        {
            timeline: [ { period, ndvi_mean, bsi_mean, mining_mean }, ... ],
            summary:  { latest_mining, ok_periods, affected_ha, critical_ha,
                        peak_score, source }
        }
    """
    return get_mining_stats_timeline()