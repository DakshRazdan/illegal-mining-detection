"""
src/verify/lease_check.py — Verifies detections against mining leases.
OWNER: Gemini (Takes over Claude Code Terminal 2)

Input: (lon, lat)
Output: LeaseStatus, lease_id, company

Uses PostGIS if available, falls back to GeoJSON file for demo speed.
"""

import json
from pathlib import Path
from shapely.geometry import Point, shape
from src.utils.logger import logger
from src.types import LeaseStatus

# PostGIS engine connection string stub, fall back directly config geojson
_GEOJSON_PATH = Path("config/lease_boundaries/jharkhand_sample.geojson")
_LEASE_POLYGONS = []

def load_leases():
    if not _LEASE_POLYGONS and _GEOJSON_PATH.exists():
        with open(_GEOJSON_PATH) as f:
            data = json.load(f)
            for feature in data.get("features", []):
                poly = shape(feature["geometry"])
                _LEASE_POLYGONS.append((poly, feature["properties"]))
        logger.debug(f"Loaded {len(_LEASE_POLYGONS)} lease boundaries from GeoJSON fallback.")

def check_lease(lon: float, lat: float) -> tuple[LeaseStatus, str | None, str | None]:
    """Check if a point is inside a mining lease."""
    load_leases()
    
    pt = Point(lon, lat)
    
    # Simple fallback: loop through GeoJSON polygons
    for poly, props in _LEASE_POLYGONS:
        if poly.contains(pt):
            lease_id = props.get("lease_id", "UNKNOWN_ID")
            company = props.get("company", "Unknown Company")
            status_str = props.get("status", "UNKNOWN").upper()
            
            if status_str == "ACTIVE":
                return LeaseStatus.INSIDE_ACTIVE, lease_id, company
            elif status_str == "EXPIRED":
                return LeaseStatus.INSIDE_EXPIRED, lease_id, company
            else:
                return LeaseStatus.UNKNOWN, lease_id, company

    return LeaseStatus.OUTSIDE, None, None
