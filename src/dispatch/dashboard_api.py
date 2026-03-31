"""
src/dispatch/dashboard_api.py — FastAPI ASGI app for the mining detection dashboard.
OWNER: Antigravity Agent 3

Run with:
    uvicorn src.dispatch.dashboard_api:app --reload --port 5000

Endpoints:
    GET /                    → Latest dashboard HTML (or status page)
    GET /map                 → Live Folium map HTML
    GET /api/health          → Health check JSON
    GET /api/detections      → GeoJSON FeatureCollection
    GET /api/verifications   → Verification results JSON
    GET /api/alerts          → All alert records JSON
    GET /api/alerts/illegal  → Illegal-only alerts JSON
    GET /api/stats           → Summary stats JSON
    GET /api/leases          → Lease boundaries GeoJSON
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Mount static and templates
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
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the amazing 3D ISRO-style dashboard."""
    loaded = _pipeline_result is not None
    run_id = _pipeline_result.run_id if _pipeline_result else "None"
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "pipeline_loaded": loaded,
            "run_id": run_id
        }
    )


@app.get("/map", response_class=HTMLResponse, include_in_schema=False)
async def live_map():
    """Render live Folium map server-side."""
    if _pipeline_result is None:
        return HTMLResponse(content="<p>No pipeline result. Run demo.py --synthetic first.</p>", status_code=503)
    from dashboard.map import build_map
    fmap = build_map(_pipeline_result)
    return HTMLResponse(content=fmap._repr_html_())


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "pipeline_loaded": _pipeline_result is not None,
        "run_id": _pipeline_result.run_id if _pipeline_result else None,
        "timestamp": datetime.utcnow().isoformat() + "Z",
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
                "properties": {k: str(v) if isinstance(v, datetime) else v for k, v in row.items()},
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
        "count": len(_pipeline_result.verifications),
        "results": [_ver_dict(v) for v in _pipeline_result.verifications],
    }


@app.get("/api/alerts")
async def get_alerts():
    if not _pipeline_result or not _pipeline_result.alerts:
        return {"count": 0, "alerts": []}
    return {
        "count": len(_pipeline_result.alerts),
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
            "run_id": None,
            "synthetic_mode": False,
            "total_detections": 0,
            "illegal_count": 0,
            "legal_count": 0,
            "total_area_ha": 0.0,
            "by_risk_level": {lvl.value: 0 for lvl in RiskLevel},
            "alert_dispatched": 0,
        }

    r = _pipeline_result
    by_risk: dict[str, int] = {lvl.value: 0 for lvl in RiskLevel}
    total_area = sum(d.area_ha for d in r.detections)

    for v in r.verifications:
        by_risk[v.risk_level.value] += 1

    dispatched = sum(
        1 for a in r.alerts
        if a.whatsapp_status == AlertStatus.DISPATCHED or a.sms_status == AlertStatus.DISPATCHED
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
async def get_leases():
    lease_path = Path("config/lease_boundaries/jharkhand_sample.geojson")
    if not lease_path.exists():
        return JSONResponse(
            {"type": "FeatureCollection", "features": [], "error": "Lease file not found"},
            status_code=404,
        )
    return json.loads(lease_path.read_text())


__all__ = ["app", "set_pipeline_result", "get_pipeline_result"]
