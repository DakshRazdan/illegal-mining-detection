"""
src/dispatch/dashboard_api.py — Flask Blueprint exposing pipeline results as JSON.
OWNER: Antigravity Agent 3

Mounted by dashboard/app.py at /api/.
All endpoints return application/json.
Reads from in-memory PipelineResult first, falls back to PostGIS if available.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, current_app, Response

from src.utils.logger import logger
from src.types import (
    AlertRecord,
    AlertStatus,
    DetectionResult,
    PipelineResult,
    RiskLevel,
    VerificationResult,
)

api = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# In-memory store — populated by the pipeline runner, read by endpoints
# ---------------------------------------------------------------------------

_pipeline_result: PipelineResult | None = None


def set_pipeline_result(result: PipelineResult) -> None:
    """Called by the pipeline runner to load results into memory for the API."""
    global _pipeline_result
    _pipeline_result = result
    logger.info("Dashboard API: pipeline result loaded | run_id={}", result.run_id)


def get_pipeline_result() -> PipelineResult | None:
    return _pipeline_result


# ---------------------------------------------------------------------------
# PostGIS read (optional — used if DB is available)
# ---------------------------------------------------------------------------

def _try_postgis_detections() -> list[dict] | None:
    """Attempt to read detections from PostGIS. Returns None if unavailable."""
    try:
        import sqlalchemy
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
        logger.debug("PostGIS unavailable for dashboard API: {}", e)
        return None


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------

def _detection_to_dict(d: DetectionResult) -> dict[str, Any]:
    return {
        "detection_id": d.detection_id,
        "lon":          d.lon,
        "lat":          d.lat,
        "area_ha":      d.area_ha,
        "mining_score": d.mining_score,
        "method":       d.method.value,
        "detected_at":  d.detected_at.isoformat() + "Z",
    }


def _verification_to_dict(v: VerificationResult) -> dict[str, Any]:
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


def _alert_to_dict(a: AlertRecord) -> dict[str, Any]:
    return {
        "alert_id":         a.alert_id,
        "detection_id":     a.detection_id,
        "risk_level":       a.risk_level.value,
        "lon":              a.lon,
        "lat":              a.lat,
        "area_ha":          a.area_ha,
        "lease_status":     a.lease_status.value,
        "risk_score":       a.risk_score,
        "whatsapp_status":  a.whatsapp_status.value,
        "sms_status":       a.sms_status.value,
        "dispatched_at":    a.dispatched_at.isoformat() + "Z" if a.dispatched_at else None,
        "district":         a.district,
        "state":            a.state,
        "message":          a.message,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@api.route("/health", methods=["GET"])
def health() -> Response:
    """System health check."""
    return jsonify({
        "status": "ok",
        "pipeline_loaded": _pipeline_result is not None,
        "run_id": _pipeline_result.run_id if _pipeline_result else None,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })


@api.route("/detections", methods=["GET"])
def get_detections() -> Response:
    """
    All detection results as a GeoJSON FeatureCollection.
    Each feature has point geometry + full detection properties.
    """
    features = []

    # Try PostGIS first
    pg_rows = _try_postgis_detections()
    if pg_rows:
        for row in pg_rows:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
                "properties": {k: str(v) if isinstance(v, datetime) else v
                               for k, v in row.items()},
            })
    elif _pipeline_result:
        for d in _pipeline_result.detections:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [d.lon, d.lat]},
                "properties": _detection_to_dict(d),
            })

    return jsonify({
        "type": "FeatureCollection",
        "count": len(features),
        "features": features,
    })


@api.route("/verifications", methods=["GET"])
def get_verifications() -> Response:
    """All verification results (legal status + risk level per detection)."""
    if not _pipeline_result or not _pipeline_result.verifications:
        return jsonify({"count": 0, "results": []})

    return jsonify({
        "count": len(_pipeline_result.verifications),
        "results": [_verification_to_dict(v) for v in _pipeline_result.verifications],
    })


@api.route("/alerts", methods=["GET"])
def get_alerts() -> Response:
    """All dispatched alert records."""
    if not _pipeline_result or not _pipeline_result.alerts:
        return jsonify({"count": 0, "alerts": []})

    return jsonify({
        "count": len(_pipeline_result.alerts),
        "alerts": [_alert_to_dict(a) for a in _pipeline_result.alerts],
    })


@api.route("/alerts/illegal", methods=["GET"])
def get_illegal_alerts() -> Response:
    """Only illegal activity alerts (CRITICAL + HIGH risk level)."""
    if not _pipeline_result:
        return jsonify({"count": 0, "alerts": []})

    illegal_levels = {AlertStatus.DISPATCHED, AlertStatus.FAILED, AlertStatus.PENDING}
    illegal_alerts = [
        a for a in _pipeline_result.alerts
        if a.risk_level in {RiskLevel.CRITICAL, RiskLevel.HIGH}
        and a.whatsapp_status in illegal_levels
    ]

    return jsonify({
        "count": len(illegal_alerts),
        "alerts": [_alert_to_dict(a) for a in illegal_alerts],
    })


@api.route("/stats", methods=["GET"])
def get_stats() -> Response:
    """
    Summary statistics for the dashboard header stats bar.
    Returns counts per risk level, total area, and run metadata.
    """
    if not _pipeline_result:
        return jsonify({
            "run_id": None,
            "synthetic_mode": False,
            "total_detections": 0,
            "illegal_count": 0,
            "legal_count": 0,
            "total_area_ha": 0.0,
            "by_risk_level": {lvl.value: 0 for lvl in RiskLevel},
            "alert_dispatched": 0,
        })

    r = _pipeline_result
    by_risk: dict[str, int] = {lvl.value: 0 for lvl in RiskLevel}
    total_area = 0.0

    for v in r.verifications:
        by_risk[v.risk_level.value] += 1

    for d in r.detections:
        total_area += d.area_ha

    dispatched = sum(
        1 for a in r.alerts
        if a.whatsapp_status == AlertStatus.DISPATCHED
        or a.sms_status == AlertStatus.DISPATCHED
    )

    return jsonify({
        "run_id":            r.run_id,
        "aoi_name":          r.aoi_name,
        "synthetic_mode":    r.synthetic_mode,
        "total_detections":  len(r.detections),
        "illegal_count":     r.illegal_count,
        "legal_count":       r.legal_count,
        "total_area_ha":     round(total_area, 2),
        "by_risk_level":     by_risk,
        "alert_dispatched":  dispatched,
        "started_at":        r.started_at.isoformat() + "Z",
        "completed_at":      r.completed_at.isoformat() + "Z" if r.completed_at else None,
    })


@api.route("/leases", methods=["GET"])
def get_leases() -> Response:
    """
    Lease boundaries as GeoJSON FeatureCollection.
    Reads from config/lease_boundaries/jharkhand_sample.geojson.
    """
    lease_path = Path("config/lease_boundaries/jharkhand_sample.geojson")
    if not lease_path.exists():
        return jsonify({"type": "FeatureCollection", "features": [], "error": "Lease file not found"})

    with open(lease_path) as f:
        data = json.load(f)

    return jsonify(data)


__all__ = ["api", "set_pipeline_result", "get_pipeline_result"]
