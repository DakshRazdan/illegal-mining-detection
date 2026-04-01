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
    aoi:          str   = Query("jharkhand"),
    period_index: int   = Query(-1),
    threshold:    float = Query(0.45, ge=0.0, le=1.0),
):
    # Priority 1: Colab real ML results (replaces ALL hardcoded dots)
    try:
        from src.dispatch.colab_bridge import is_loaded, extract_hotspots, get_detection_stats
        if is_loaded():
            hotspots = extract_hotspots(threshold=threshold, max_hotspots=300)
            if hotspots:
                features = [{"type":"Feature","geometry":{"type":"Point","coordinates":[h["lon"],h["lat"]]},"properties":{"disturbance":h["disturbance"],"lat":h["lat"],"lon":h["lon"],"area_ha":h["area_ha"],"status":h["status"],"risk_level":h["risk_level"],"risk_score":h["risk_score"],"district":h["district"],"state":"Jharkhand","method":h["method"],"lease_name":"OSM verified" if h["status"]=="approved" else "No lease found"}} for h in hotspots]
                stats = get_detection_stats()
                illegal = sum(1 for h in hotspots if h["status"]=="illegal")
                high_risk = sum(1 for h in hotspots if h["risk_level"] in ("CRITICAL","HIGH"))
                return JSONResponse({"aoi":aoi,"geojson":{"type":"FeatureCollection","features":features},"stats":{"total":len(features),"illegal":illegal,"approved":len(features)-illegal,"high_risk_pct":round(high_risk/max(len(features),1)*100,1),"n_hotspots":len(features),"affected_area_ha":stats.get("affected_area_ha"),"peak_score":stats.get("peak_score"),"source":"colab_spectral_rf"}})
    except Exception as e:
        logger.warning("Colab bridge failed: {}", e)

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


@router.get("/overlay/{aoi}/{index_name}")
def get_overlay(aoi: str, index_name: str, period_idx: int = Query(11)):
    """
    Returns base64 PNG overlay for any AOI and index.
    - Jharkhand: uses real Sentinel-2 cached data
    - Odisha/CG: generates synthetic but realistic overlay from OSM mine locations
    """
    _ensure_periods_loaded()

    # For Jharkhand use real data
    if aoi == "jharkhand":
        ok = [r for r in _PERIODS_CACHE if r.get("status") == "ok"]
        if ok:
            period = ok[min(period_idx, len(ok)-1)]
            key = f"{index_name}_png_b64"
            img = period.get(key)
            if img:
                return JSONResponse({"png_b64": img, "source": "sentinel2", "aoi": aoi})

    # For Odisha/CG generate synthetic overlay from OSM boundaries
    try:
        import io, base64, json, numpy as np
        from pathlib import Path
        from PIL import Image
        from matplotlib import cm
        from scipy.ndimage import gaussian_filter

        lease_path = Path(f"config/lease_boundaries/{aoi}.geojson")
        if not lease_path.exists():
            return JSONResponse({"error": "No boundary data"}, status_code=404)

        features = json.loads(lease_path.read_text()).get("features", [])

        bounds_map = {
            "jharkhand":    [85.8, 23.5, 86.2, 23.8],
            "odisha":       [84.0, 20.0, 86.0, 21.5],
            "chhattisgarh": [81.5, 21.5, 83.5, 23.0],
        }
        bounds = bounds_map.get(aoi, [85.8, 23.5, 86.2, 23.8])
        min_lon, min_lat, max_lon, max_lat = bounds

        H, W = 128, 128

        # Base layer: natural vegetation for the region
        base_ndvi = {
            "jharkhand": 0.45, "odisha": 0.50, "chhattisgarh": 0.52
        }.get(aoi, 0.48)

        score_map = np.full((H, W), base_ndvi, dtype=float)
        score_map += np.random.normal(0, 0.03, (H, W))

        # Paint mine signatures on the map
        for f in features:
            geom = f.get("geometry", {})
            if geom.get("type") == "Polygon":
                coords = geom["coordinates"][0]
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                cx = np.mean(lons); cy = np.mean(lats)
            elif geom.get("type") == "Point":
                cx, cy = geom["coordinates"][0], geom["coordinates"][1]
            else:
                continue

            if not (min_lon <= cx <= max_lon and min_lat <= cy <= max_lat):
                continue

            px = int((cx - min_lon) / (max_lon - min_lon) * W)
            py = int((max_lat - cy) / (max_lat - min_lat) * H)
            px = max(1, min(W-2, px))
            py = max(1, min(H-2, py))
            r = max(2, min(8, int(2 + np.random.uniform(0, 4))))

            # Mine signature depends on index type
            if index_name == "ndvi":
                val = 0.05 + np.random.uniform(0, 0.10)  # low vegetation
            elif index_name == "bsi":
                val = 0.70 + np.random.uniform(0, 0.25)  # high bare soil
            elif index_name == "ndwi":
                val = 0.15 + np.random.uniform(0, 0.20)  # some water
            elif index_name == "turbidity":
                val = 0.60 + np.random.uniform(0, 0.30)  # high turbidity near mines
            elif index_name == "mining":
                val = 0.65 + np.random.uniform(0, 0.30)  # high mining probability
            else:
                val = 0.5

            y1,y2 = max(0,py-r), min(H,py+r)
            x1,x2 = max(0,px-r), min(W,px+r)
            score_map[y1:y2, x1:x2] = val

        score_map = gaussian_filter(score_map, sigma=1.5)
        score_map = np.clip(score_map, 0, 1)

        cmap_map = {
            "ndvi": "RdYlGn", "bsi": "YlOrBr",
            "ndwi": "Blues", "turbidity": "PuRd", "mining": "hot_r"
        }
        cmap_name = cmap_map.get(index_name, "viridis")
        rgb = (cm.get_cmap(cmap_name)(score_map)[:, :, :3] * 255).astype(np.uint8)
        img = Image.fromarray(rgb).resize((256, 256), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return JSONResponse({"png_b64": b64, "source": "synthetic_osm", "aoi": aoi})

    except Exception as e:
        logger.error("Overlay generation failed: {}", e)
        return JSONResponse({"error": str(e)}, status_code=500)