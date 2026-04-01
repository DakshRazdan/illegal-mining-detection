"""
src/dispatch/mining_endpoints.py
FastAPI router — serves real ML detections from npz_detector.py

Endpoints:
  GET /api/mining/health
  GET /api/mining/map?aoi=jharkhand
  GET /api/mining/detections?aoi=jharkhand
  GET /api/mining/stats
  GET /api/mining/analyze/{period_index}
"""
from __future__ import annotations

import io as _io
import base64
import numpy as np
from pathlib import Path
from functools import lru_cache

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from loguru import logger

router = APIRouter(tags=["Mining ML"])

# ── In-memory detection cache (populated lazily) ─────────────────────────────
_DETECTION_CACHE: dict[str, list[dict]] = {}
_PERIODS_CACHE: list[dict] = []
_LOADED = False


def _ensure_periods_loaded():
    global _PERIODS_CACHE, _LOADED
    if _LOADED:
        return
    cache_dir = Path("data/temporal")
    _PERIODS_CACHE = []
    try:
        from src.ingest.temporal_fetch import DEFAULT_PERIODS
        for start, end, label in DEFAULT_PERIODS:
            f = cache_dir / f"{label.replace(' ','_')}.npz"
            if f.exists():
                try:
                    data = np.load(f, allow_pickle=True)
                    _PERIODS_CACHE.append(dict(data["result"].item()))
                except Exception as e:
                    logger.warning("Cache load {} failed: {}", label, e)
    except ImportError:
        pass
    _LOADED = True
    logger.info("Mining endpoints: {} cached periods", len(_PERIODS_CACHE))


def _ensure_detections(aoi_key: str):
    """Run ML detection for an AOI if not already cached."""
    if aoi_key in _DETECTION_CACHE:
        return
    try:
        from src.detect.npz_detector import run_detection_for_aoi
        detections = run_detection_for_aoi(aoi_key=aoi_key)
        _DETECTION_CACHE[aoi_key] = detections
        logger.info("Detection cache populated for {}: {} results", aoi_key, len(detections))
    except Exception as e:
        logger.error("Detection failed for {}: {}", aoi_key, e)
        _DETECTION_CACHE[aoi_key] = []


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/health")
def mining_health():
    _ensure_periods_loaded()
    cached_aois = list(_DETECTION_CACHE.keys())
    return {
        "status": "ok",
        "cached_periods": len(_PERIODS_CACHE),
        "periods_with_data": sum(1 for r in _PERIODS_CACHE if r.get("status") == "ok"),
        "detection_cache": {k: len(v) for k, v in _DETECTION_CACHE.items()},
        "available_aois": ["jharkhand", "odisha", "chhattisgarh"],
    }


@router.get("/map")
def get_mining_map(
    aoi:       str   = Query("jharkhand"),
    threshold: float = Query(0.45, ge=0.0, le=1.0),
):
    """
    Returns GeoJSON hotspots from real ML detection for specified AOI.
    Falls back to OSM seeding if no Sentinel-2 cache available.
    """
    _ensure_detections(aoi)
    detections = _DETECTION_CACHE.get(aoi, [])

    # Filter by threshold
    filtered = [d for d in detections if d.get("mining_score", 0) >= threshold]

    features = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [d["lon"], d["lat"]]},
        "properties": {
            "disturbance":  d.get("mining_score", 0),
            "lat":          d["lat"],
            "lon":          d["lon"],
            "area_ha":      d.get("area_ha", 0),
            "status":       d.get("status", "suspected"),
            "risk_level":   d.get("risk_level", "MEDIUM"),
            "risk_score":   d.get("risk_score", 50),
            "lease_name":   d.get("lease_name", "—"),
            "district":     d.get("district", "—"),
            "state":        d.get("state", "—"),
            "method":       d.get("method", "—"),
            "baseline":     d.get("baseline", "—"),
            "current":      d.get("current", "—"),
            "detected_at":  d.get("detected_at", "—"),
        }
    } for d in filtered]

    illegal   = sum(1 for d in filtered if d.get("status") == "illegal")
    approved  = sum(1 for d in filtered if d.get("status") == "approved")
    high_risk = sum(1 for d in filtered if d.get("risk_level") in ("CRITICAL", "HIGH"))

    ok_periods = [r for r in _PERIODS_CACHE if r.get("status") == "ok"]
    latest = ok_periods[-1] if ok_periods else {}

    return JSONResponse({
        "aoi":    aoi,
        "date":   latest.get("scene_date"),
        "label":  latest.get("label"),
        "geojson": {"type": "FeatureCollection", "features": features},
        "stats": {
            "total":         len(features),
            "illegal":       illegal,
            "approved":      approved,
            "suspected":     len(features) - illegal - approved,
            "high_risk_pct": round(high_risk / max(len(features), 1) * 100, 1),
            "n_hotspots":    len(features),
            "ndvi_mean":     latest.get("ndvi_mean"),
            "bsi_mean":      latest.get("bsi_mean"),
            "mining_mean":   latest.get("mining_mean"),
            "source":        "spectral_rf_npz" if _PERIODS_CACHE else "osm_seed",
        },
    })


@router.get("/detections")
def get_detections(aoi: str = Query("jharkhand")):
    """Full detection list for an AOI with all properties."""
    _ensure_detections(aoi)
    return {
        "aoi":        aoi,
        "count":      len(_DETECTION_CACHE.get(aoi, [])),
        "detections": _DETECTION_CACHE.get(aoi, []),
    }


@router.get("/stats")
def get_mining_stats():
    """Time-series stats from cached periods for Analytics panel."""
    _ensure_periods_loaded()
    timeline = [{
        "label":       r.get("label"),
        "scene_date":  r.get("scene_date"),
        "status":      r.get("status"),
        "ndvi_mean":   r.get("ndvi_mean"),
        "bsi_mean":    r.get("bsi_mean"),
        "mining_mean": r.get("mining_mean"),
    } for r in _PERIODS_CACHE]

    ok = [r for r in timeline if r["status"] == "ok"]
    latest = ok[-1] if ok else {}

    return {
        "timeline": timeline,
        "summary": {
            "total_periods": len(timeline),
            "ok_periods":    len(ok),
            "latest_label":  latest.get("label"),
            "latest_ndvi":   latest.get("ndvi_mean"),
            "latest_bsi":    latest.get("bsi_mean"),
            "latest_mining": latest.get("mining_mean"),
        }
    }


@router.get("/analyze/{period_index}")
def analyze_period(period_index: int, baseline_index: int = Query(0)):
    """Before/after analysis for a specific period."""
    _ensure_periods_loaded()
    ok = [r for r in _PERIODS_CACHE if r.get("status") == "ok"]
    if not ok:
        return JSONResponse({"error": "No cached periods"}, status_code=404)
    if period_index >= len(ok):
        return JSONResponse({"error": f"Max index: {len(ok)-1}"}, status_code=404)

    cur = ok[period_index]
    bas = ok[min(baseline_index, len(ok)-1)]

    def delta(key):
        return round((cur.get(key) or 0) - (bas.get(key) or 0), 4)

    return JSONResponse({
        "period":     cur.get("label"),
        "baseline":   bas.get("label"),
        "scene_date": cur.get("scene_date"),
        "cloud_cover":cur.get("cloud_cover"),
        "index_images": {
            "ndvi":      cur.get("ndvi_png_b64"),
            "bsi":       cur.get("bsi_png_b64"),
            "ndwi":      cur.get("ndwi_png_b64"),
            "turbidity": cur.get("turbidity_png_b64"),
            "mining":    cur.get("mining_png_b64"),
        },
        "stats": {
            "ndvi_mean":    cur.get("ndvi_mean"),
            "bsi_mean":     cur.get("bsi_mean"),
            "mining_mean":  cur.get("mining_mean"),
            "ndvi_delta":   delta("ndvi_mean"),
            "bsi_delta":    delta("bsi_mean"),
            "mining_delta": delta("mining_mean"),
        },
    })