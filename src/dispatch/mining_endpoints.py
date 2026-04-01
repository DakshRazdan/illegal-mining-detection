"""
src/dispatch/mining_endpoints.py
FastAPI router for ML-backed mining detection endpoints.

Mount in dashboard_api.py:
    from src.dispatch.mining_endpoints import router as mining_router
    app.include_router(mining_router, prefix="/api/mining")
"""

from __future__ import annotations

import io as _io
import base64
import numpy as np
from pathlib import Path

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

router = APIRouter(tags=["Mining ML"])

_PERIODS_CACHE: list[dict] = []
_LOADED = False


def _ensure_loaded():
    global _PERIODS_CACHE, _LOADED
    if _LOADED:
        return
    from src.ingest.temporal_fetch import DEFAULT_PERIODS
    cache_dir = Path("data/temporal")
    _PERIODS_CACHE = []
    for start, end, label in DEFAULT_PERIODS:
        cache_file = cache_dir / f"{label.replace(' ', '_')}.npz"
        if cache_file.exists():
            try:
                data = np.load(cache_file, allow_pickle=True)
                _PERIODS_CACHE.append(dict(data["result"].item()))
            except Exception as e:
                logger.warning("Cache load failed {}: {}", label, e)
    _LOADED = True
    logger.info("Mining endpoints: {} periods loaded", len(_PERIODS_CACHE))


def _extract_hotspots(result: dict, threshold: float = 0.55) -> list[dict]:
    if not result.get("mining_png_b64"):
        return []
    try:
        from PIL import Image
        img_bytes = base64.b64decode(result["mining_png_b64"])
        img = Image.open(_io.BytesIO(img_bytes)).convert("L")
        arr = np.array(img, dtype=float) / 255.0
    except Exception as e:
        logger.warning("Decode failed: {}", e)
        return []

    from src.ingest.temporal_fetch import AOI_BOUNDS
    min_lon, min_lat, max_lon, max_lat = AOI_BOUNDS
    H, W = arr.shape
    rows, cols = np.where(arr >= threshold)
    if len(rows) == 0:
        return []

    scores = arr[rows, cols]
    order  = np.argsort(scores)[::-1][:150]
    rows, cols, scores = rows[order], cols[order], scores[order]

    features = []
    for r, c, score in zip(rows, cols, scores):
        lat = max_lat - (r / H) * (max_lat - min_lat)
        lon = min_lon + (c / W) * (max_lon - min_lon)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon,5), round(lat,5)]},
            "properties": {
                "disturbance": round(float(score), 3),
                "lat": round(float(lat), 5),
                "lon": round(float(lon), 5),
                "period": result.get("label", ""),
                "scene_date": result.get("scene_date", ""),
            }
        })
    return features


@router.get("/health")
def mining_health():
    _ensure_loaded()
    return {
        "status": "ok",
        "cached_periods": len(_PERIODS_CACHE),
        "periods_with_data": sum(1 for r in _PERIODS_CACHE if r.get("status") == "ok"),
    }


@router.get("/map")
def get_mining_map(
    period_index: int   = Query(-1),
    threshold:    float = Query(0.55, ge=0.0, le=1.0),
):
    _ensure_loaded()
    ok = [r for r in _PERIODS_CACHE if r.get("status") == "ok"]

    if not ok:
        return JSONResponse({
            "date": None,
            "geojson": {"type": "FeatureCollection", "features": []},
            "stats": {"high_risk_pct": 0, "n_hotspots": 0, "source": "no_data"},
        })

    result   = ok[period_index]
    features = _extract_hotspots(result, threshold)
    high     = sum(1 for f in features if f["properties"]["disturbance"] > 0.7)

    return JSONResponse({
        "date":    result.get("scene_date"),
        "label":   result.get("label"),
        "geojson": {"type": "FeatureCollection", "features": features},
        "stats": {
            "high_risk_pct": round(high / max(len(features),1) * 100, 1),
            "n_hotspots":    len(features),
            "ndvi_mean":     result.get("ndvi_mean"),
            "bsi_mean":      result.get("bsi_mean"),
            "mining_mean":   result.get("mining_mean"),
            "source":        "sentinel2_spectral_rf",
        },
    })


@router.get("/analyze/{period_index}")
def analyze_period(period_index: int, baseline_index: int = Query(0)):
    _ensure_loaded()
    ok = [r for r in _PERIODS_CACHE if r.get("status") == "ok"]

    if not ok:
        raise HTTPException(status_code=404, detail="No cached periods. Run prefetch_temporal.py first.")
    if period_index >= len(ok):
        raise HTTPException(status_code=404, detail=f"Max index: {len(ok)-1}")

    cur = ok[period_index]
    bas = ok[min(baseline_index, len(ok)-1)]

    def delta(key):
        a = cur.get(key) or 0
        b = bas.get(key) or 0
        return round(a - b, 4)

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
        "hotspots": _extract_hotspots(cur),
    })


@router.get("/stats")
def get_mining_stats():
    _ensure_loaded()
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