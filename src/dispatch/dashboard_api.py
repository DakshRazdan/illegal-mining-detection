"""
src/dispatch/dashboard_api.py — FastAPI ASGI app for the mining detection dashboard.

Run with:
    uvicorn src.dispatch.dashboard_api:app --reload --port 5000

Endpoints:
    GET  /                          → Latest dashboard HTML (or status page)
    GET  /map                       → Live Folium map HTML
    GET  /api/health                → Health check JSON
    GET  /api/detections            → GeoJSON FeatureCollection
    GET  /api/verifications         → Verification results JSON
    GET  /api/alerts                → All alert records JSON
    GET  /api/alerts/illegal        → Illegal-only alerts JSON
    GET  /api/stats                 → Summary stats JSON
    GET  /api/leases                → Lease boundaries GeoJSON
    GET  /api/temporal/periods      → Temporal period metadata
    GET  /api/temporal/frame/{idx}  → Single temporal frame (PNG overlays)
    POST /api/colab/ingest          → Upload Colab .npz arrays → powers map overlays
    GET  /api/colab/status          → Check whether Colab data is loaded
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.utils.logger import logger
from src.types import (
    AlertRecord,
    AlertStatus,
    DetectionResult,
    PipelineResult,
    RiskLevel,
    VerificationResult,
)

# ---------------------------------------------------------------------------
# FastAPI app — MUST be named "app" at module level for uvicorn
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mining Watch API",
    description="Autonomous Illegal Mining Detection System — Jharkhand, India",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Routers ────────────────────────────────────────────────────────────────
from src.dispatch.mining_endpoints import router as mining_router
app.include_router(mining_router, prefix="/api/mining")

# ── CORS ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Static files & templates ───────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")
templates = Jinja2Templates(directory="dashboard/templates")


# ---------------------------------------------------------------------------
# In-memory pipeline result store
# ---------------------------------------------------------------------------

_pipeline_result: PipelineResult | None = None


def set_pipeline_result(result: PipelineResult) -> None:
    """Load a PipelineResult into memory so API endpoints can serve it."""
    global _pipeline_result
    _pipeline_result = result
    logger.info("Dashboard API: pipeline result loaded | run_id={}", result.run_id)


def get_pipeline_result() -> PipelineResult | None:
    return _pipeline_result


# ---------------------------------------------------------------------------
# PostGIS read (optional)
# ---------------------------------------------------------------------------

def _try_postgis_detections() -> list[dict] | None:
    """Read detections from PostGIS. Returns None if DB unavailable."""
    try:
        from sqlalchemy import create_engine, text
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return None
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT detection_id, lon, lat, area_ha, mining_score, method, detected_at "
                "FROM detections ORDER BY detected_at DESC LIMIT 500"
            ))
            return [dict(r._mapping) for r in rows]
    except Exception as e:
        logger.debug("PostGIS unavailable: {}", e)
        return None


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------

def _det_dict(d: DetectionResult) -> dict[str, Any]:
    return {
        "detection_id": d.detection_id,
        "lon":          d.lon,
        "lat":          d.lat,
        "area_ha":      d.area_ha,
        "mining_score": d.mining_score,
        "method":       d.method.value,
        "detected_at":  d.detected_at.isoformat() + "Z",
    }


def _ver_dict(v: VerificationResult) -> dict[str, Any]:
    return {
        "detection_id":  v.detection_id,
        "lease_status":  v.lease_status.value,
        "lease_id":      v.lease_id,
        "lease_company": v.lease_company,
        "ec_valid":      v.ec_valid,
        "ec_id":         v.ec_id,
        "land_type":     v.land_type,
        "risk_score":    v.risk_score,
        "risk_level":    v.risk_level.value,
        "is_illegal":    v.is_illegal,
        "verified_at":   v.verified_at.isoformat() + "Z",
        "notes":         v.notes,
    }


def _alert_dict(a: AlertRecord) -> dict[str, Any]:
    return {
        "alert_id":        a.alert_id,
        "detection_id":    a.detection_id,
        "risk_level":      a.risk_level.value,
        "lon":             a.lon,
        "lat":             a.lat,
        "area_ha":         a.area_ha,
        "lease_status":    a.lease_status.value,
        "risk_score":      a.risk_score,
        "whatsapp_status": a.whatsapp_status.value,
        "sms_status":      a.sms_status.value,
        "dispatched_at":   a.dispatched_at.isoformat() + "Z" if a.dispatched_at else None,
        "district":        a.district,
        "state":           a.state,
        "message":         a.message,
    }


# ---------------------------------------------------------------------------
# Routes — HTML pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main dashboard."""
    loaded = _pipeline_result is not None
    run_id = _pipeline_result.run_id if _pipeline_result else "None"
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "pipeline_loaded": loaded, "run_id": run_id},
    )


@app.get("/openmine", response_class=HTMLResponse, include_in_schema=False)
async def openmine_dashboard():
    """Serve the OpenMine public-facing dashboard."""
    content = Path("dashboard/static/openmine.html").read_text(encoding="utf-8")
    return HTMLResponse(content=content)


@app.get("/map", response_class=HTMLResponse, include_in_schema=False)
async def live_map():
    """Serve the static Folium map generated by the pipeline."""
    latest = Path("results/demo/latest.html")
    if latest.exists():
        return HTMLResponse(content=latest.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<p>No map generated yet. Run demo.py --synthetic first.</p>",
        status_code=503,
    )


# ---------------------------------------------------------------------------
# Routes — Core API
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    from src.dispatch.colab_bridge import is_loaded as colab_loaded
    return {
        "status":           "ok",
        "pipeline_loaded":  _pipeline_result is not None,
        "colab_loaded":     colab_loaded(),
        "run_id":           _pipeline_result.run_id if _pipeline_result else None,
        "timestamp":        datetime.utcnow().isoformat() + "Z",
    }


@app.get("/api/detections")
async def get_detections():
    """All detections as GeoJSON FeatureCollection."""
    features = []

    pg_rows = _try_postgis_detections()
    if pg_rows:
        for row in pg_rows:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
                "properties": {
                    k: str(v) if isinstance(v, datetime) else v
                    for k, v in row.items()
                },
            })
    elif _pipeline_result:
        for d in _pipeline_result.detections:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [d.lon, d.lat]},
                "properties": _det_dict(d),
            })

    return {"type": "FeatureCollection", "count": len(features), "features": features}


@app.get("/api/verifications")
async def get_verifications():
    if not _pipeline_result or not _pipeline_result.verifications:
        return {"count": 0, "results": []}
    return {
        "count":   len(_pipeline_result.verifications),
        "results": [_ver_dict(v) for v in _pipeline_result.verifications],
    }


@app.get("/api/alerts")
async def get_alerts():
    if not _pipeline_result or not _pipeline_result.alerts:
        return {"count": 0, "alerts": []}
    return {
        "count":  len(_pipeline_result.alerts),
        "alerts": [_alert_dict(a) for a in _pipeline_result.alerts],
    }


@app.get("/api/alerts/illegal")
async def get_illegal_alerts():
    if not _pipeline_result:
        return {"count": 0, "alerts": []}
    illegal = [
        a for a in _pipeline_result.alerts
        if a.risk_level in {RiskLevel.CRITICAL, RiskLevel.HIGH}
        and a.whatsapp_status != AlertStatus.SUPPRESSED
    ]
    return {"count": len(illegal), "alerts": [_alert_dict(a) for a in illegal]}


@app.get("/api/stats")
async def get_stats():
    if not _pipeline_result:
        return {
            "run_id":           None,
            "synthetic_mode":   False,
            "total_detections": 0,
            "illegal_count":    0,
            "legal_count":      0,
            "total_area_ha":    0.0,
            "by_risk_level":    {lvl.value: 0 for lvl in RiskLevel},
            "alert_dispatched": 0,
        }

    r = _pipeline_result
    by_risk: dict[str, int] = {lvl.value: 0 for lvl in RiskLevel}
    total_area = sum(d.area_ha for d in r.detections)

    for v in r.verifications:
        by_risk[v.risk_level.value] += 1

    dispatched = sum(
        1 for a in r.alerts
        if a.whatsapp_status == AlertStatus.DISPATCHED
        or a.sms_status == AlertStatus.DISPATCHED
    )

    return {
        "run_id":           r.run_id,
        "aoi_name":         r.aoi_name,
        "synthetic_mode":   r.synthetic_mode,
        "total_detections": len(r.detections),
        "illegal_count":    r.illegal_count,
        "legal_count":      r.legal_count,
        "total_area_ha":    round(total_area, 2),
        "by_risk_level":    by_risk,
        "alert_dispatched": dispatched,
        "started_at":       r.started_at.isoformat() + "Z",
        "completed_at":     r.completed_at.isoformat() + "Z" if r.completed_at else None,
    }


@app.get("/api/leases")
async def get_leases(region: str = "jharkhand"):
    lease_path = Path(f"config/lease_boundaries/{region}.geojson")
    if not lease_path.exists():
        lease_path = Path("config/lease_boundaries/india_coal_belt.geojson")
    if not lease_path.exists():
        return JSONResponse(
            {"type": "FeatureCollection", "features": []},
            status_code=404,
        )
    return json.loads(lease_path.read_text())


# ---------------------------------------------------------------------------
# Routes — Temporal (reads from colab_bridge when loaded, else disk cache)
# ---------------------------------------------------------------------------

@app.get("/api/temporal/periods")
async def get_temporal_periods():
    """
    Returns period metadata for the frontend time-slider.

    Priority:
      1. Colab-ingested temporal_dates + temporal_scores
      2. Cached .npz files on disk (original behaviour)
      3. 12-quarter synthetic fallback
    """
    from src.dispatch.colab_bridge import (
        get_temporal_periods as colab_periods,
        is_loaded,
    )

    if is_loaded():
        periods = colab_periods()
        return {
            "periods": periods,
            "total":   len([p for p in periods if p.get("status") == "ok"]),
            "aoi_bounds": [85.8, 23.5, 86.2, 23.8],
            "source": "colab_ingest",
        }

    # Original disk-cache path
    try:
        from src.ingest.temporal_fetch import DEFAULT_PERIODS
        import numpy as np
        cache_dir = Path("data/temporal")
        results = []
        for i, (start, end, label) in enumerate(DEFAULT_PERIODS):
            cache_file = cache_dir / f"{label.replace(' ', '_')}.npz"
            if cache_file.exists():
                try:
                    data = np.load(cache_file, allow_pickle=True)
                    r = dict(data["result"].item())
                    results.append({
                        "index": i, "label": r["label"],
                        "start": r["start"], "end": r["end"],
                        "scene_date": r.get("scene_date"),
                        "ndvi_mean":  r.get("ndvi_mean"),
                        "status":     r["status"],
                    })
                except Exception:
                    results.append({"index": i, "label": label,
                                    "start": start, "end": end, "status": "error"})
            else:
                results.append({"index": i, "label": label,
                                 "start": start, "end": end, "status": "not_cached"})
        return {
            "periods":   results,
            "total":     len([r for r in results if r["status"] == "ok"]),
            "aoi_bounds": [85.8, 23.5, 86.2, 23.8],
            "source":    "disk_cache",
        }
    except ImportError:
        # Colab bridge synthetic fallback
        from src.dispatch.colab_bridge import get_temporal_periods as colab_periods
        periods = colab_periods()
        return {
            "periods":    periods,
            "total":      len(periods),
            "aoi_bounds": [85.8, 23.5, 86.2, 23.8],
            "source":     "synthetic",
        }


@app.get("/api/temporal/frame/{index}")
async def get_temporal_frame(index: int):
    """
    Return a single temporal frame with PNG overlays + metadata.

    Priority:
      1. Colab-ingested arrays  → renders in colab_bridge.py
      2. Original disk-cache fetch → src/ingest/temporal_fetch.py
    """
    from src.dispatch.colab_bridge import (
        get_temporal_frame as colab_frame,
        is_loaded,
    )

    if is_loaded():
        frame = colab_frame(index)
        return {
            "index":           frame.get("index", index),
            "label":           frame.get("label"),
            "scene_date":      frame.get("scene_date"),
            "ndvi_png_b64":    frame.get("ndvi_png_b64"),
            "bsi_png_b64":     frame.get("bsi_png_b64"),
            "ndwi_png_b64":    frame.get("ndwi_png_b64"),
            "turbidity_png_b64": frame.get("turbidity_png_b64"),
            "mining_png_b64":  frame.get("mining_png_b64"),
            "rgb_png_b64":     frame.get("rgb_png_b64"),
            "ndvi_mean":       frame.get("ndvi_mean"),
            "bsi_mean":        frame.get("bsi_mean"),
            "mining_mean":     frame.get("mining_mean"),
            "status":          frame.get("status", "ok"),
            "source":          "colab_ingest",
        }

    # Original path
    try:
        from src.ingest.temporal_fetch import fetch_ndvi_composite, DEFAULT_PERIODS
        if index < 0 or index >= len(DEFAULT_PERIODS):
            return {"error": "Index out of range"}
        start, end, label = DEFAULT_PERIODS[index]
        result = fetch_ndvi_composite(start, end, label)
        return {
            "index":           index,
            "label":           result["label"],
            "scene_date":      result.get("scene_date"),
            "ndvi_png_b64":    result.get("ndvi_png_b64"),
            "bsi_png_b64":     result.get("bsi_png_b64"),
            "ndwi_png_b64":    result.get("ndwi_png_b64"),
            "turbidity_png_b64": result.get("turbidity_png_b64"),
            "mining_png_b64":  result.get("mining_png_b64"),
            "rgb_png_b64":     result.get("rgb_png_b64"),
            "ndvi_mean":       result.get("ndvi_mean"),
            "bsi_mean":        result.get("bsi_mean"),
            "mining_mean":     result.get("mining_mean"),
            "cloud_cover":     result.get("cloud_cover"),
            "status":          result["status"],
            "error":           result.get("error"),
            "source":          "sentinel2",
        }
    except ImportError:
        from src.dispatch.colab_bridge import get_temporal_frame as colab_frame
        return colab_frame(index)


# ---------------------------------------------------------------------------
# Routes — Colab ingest
# ---------------------------------------------------------------------------

@app.post("/api/colab/ingest")
async def colab_ingest(file: UploadFile = File(...)):
    """
    Upload a .npz file exported from the Colab notebook.

    Expected arrays (include whichever are available):
        ndvi_a, ndvi_b          — NDVI after/before (h × w float32)
        bsi_a,  bsi_b           — Bare Soil Index after/before
        ndwi_a, ndwi_b          — NDWI after/before
        nbr_a,  nbr_b           — NBR after/before
        mining_score            — 4-index fused probability map
        mining_score_v2         — 6-index fused probability map (preferred)
        temporal_dates          — 1-D string array  e.g. ["2019", "2020", …]
        temporal_scores         — 1-D float array of mean mining scores
        labels_a, labels_b      — K-Means cluster label arrays
        affected_area_ha        — scalar float
        critical_area_ha        — scalar float
        peak_score              — scalar float

    Usage from Colab:
        import numpy as np, requests

        np.savez_compressed("/tmp/openmine_payload.npz",
            ndvi_a=ndvi_a, ndvi_b=ndvi_b,
            bsi_a=bsi_a, bsi_b=bsi_b,
            ndwi_a=ndwi_a, ndwi_b=ndwi_b,
            nbr_a=nbr_a, nbr_b=nbr_b,
            mining_score=mining_score,
            mining_score_v2=mining_score_v2,
            temporal_dates=np.array([str(d.year) for d in dates]),
            temporal_scores=np.array(scores),
            affected_area_ha=affected_area,
            critical_area_ha=critical,
            peak_score=float(mining_score_v2.max()),
        )

        with open("/tmp/openmine_payload.npz", "rb") as f:
            r = requests.post(
                "https://web-production-f8923.up.railway.app/api/colab/ingest",
                files={"file": ("payload.npz", f, "application/octet-stream")},
            )
        print(r.json())
    """
    if not file.filename.endswith(".npz"):
        return JSONResponse(
            {"error": "Only .npz files accepted. Use np.savez_compressed()."},
            status_code=400,
        )

    try:
        raw = await file.read()
    except Exception as exc:
        return JSONResponse({"error": f"Failed to read upload: {exc}"}, status_code=400)

    from src.dispatch.colab_bridge import ingest_npz
    try:
        summary = ingest_npz(raw)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    logger.success(
        "Colab ingest complete | keys={} | shape={}",
        summary["loaded_keys"],
        summary["shape"],
    )

    return {
        "status":      "ok",
        "loaded_keys": summary["loaded_keys"],
        "shape":       summary["shape"],
        "message":     (
            f"Successfully ingested {len(summary['loaded_keys'])} arrays. "
            "Map overlays, hotspots, and stats are now live."
        ),
    }


@app.get("/api/colab/status")
async def colab_status():
    """Check whether Colab data is loaded and what's available."""
    from src.dispatch.colab_bridge import get_store, is_loaded
    store = get_store()
    available = [k for k, v in store.items() if v is not None and k != "loaded"]
    shape = None
    for k in ("mining_score_v2", "mining_score", "ndvi_a"):
        if store.get(k) is not None:
            import numpy as np
            arr = store[k]
            if hasattr(arr, "shape"):
                shape = list(arr.shape)
            break
    return {
        "loaded":          is_loaded(),
        "available_keys":  available,
        "array_shape":     shape,
        "aoi_bounds":      store["aoi_bounds"],
        "affected_area_ha": store.get("affected_area_ha"),
        "peak_score":      store.get("peak_score"),
    }


__all__ = ["app", "set_pipeline_result", "get_pipeline_result"]