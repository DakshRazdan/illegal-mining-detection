"""
dashboard/map.py — Folium map builder for the mining detection dashboard.
OWNER: Antigravity Agent 4

Generates a Folium HTML map with:
  - CartoDB dark_matter basemap (ISRO mission control aesthetic)
  - Lease boundary polygons (saffron fill, 0.2 opacity)
  - Detection markers (color-coded by risk level)
  - Popup cards with full verification chain info
  - Layer controls for toggling lease / detection overlays

Entry point: build_map(result: PipelineResult) -> folium.Map
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import folium
from folium.plugins import MarkerCluster, HeatMap

from src.utils.logger import logger
from src.utils.config import SETTINGS
from src.types import (
    AlertRecord,
    AlertStatus,
    DetectionResult,
    PipelineResult,
    RiskLevel,
    VerificationResult,
)


# ---------------------------------------------------------------------------
# Risk level colours (matches design system)
# ---------------------------------------------------------------------------

_RISK_COLOUR = {
    RiskLevel.CRITICAL: "#FF4444",   # danger red
    RiskLevel.HIGH:     "#FF9933",   # saffron
    RiskLevel.MEDIUM:   "#FFD700",   # gold/yellow
    RiskLevel.LOW:      "#00C853",   # success green
}

_RISK_EMOJI = {
    RiskLevel.CRITICAL: "🚨",
    RiskLevel.HIGH:     "⚠️",
    RiskLevel.MEDIUM:   "🟡",
    RiskLevel.LOW:      "🟢",
}


# ---------------------------------------------------------------------------
# Popup HTML builder
# ---------------------------------------------------------------------------

def _build_popup(
    d: DetectionResult,
    v: Optional[VerificationResult],
    a: Optional[AlertRecord],
) -> str:
    risk_colour = _RISK_COLOUR.get(v.risk_level if v else RiskLevel.LOW, "#FFFFFF")
    risk_label  = v.risk_level.value if v else "UNKNOWN"
    emoji       = _RISK_EMOJI.get(v.risk_level if v else RiskLevel.LOW, "❓")

    alert_row = ""
    if a:
        status = "✅ Dispatched" if a.whatsapp_status == AlertStatus.DISPATCHED else "📋 Console log"
        alert_row = f"<tr><td><b>Alert</b></td><td>{status}</td></tr>"

    ec_row = ""
    if v:
        if v.ec_valid is False:
            ec_row = "<tr><td><b>EC Status</b></td><td>❌ No valid clearance</td></tr>"
        elif v.ec_valid is True:
            ec_row = f"<tr><td><b>EC ID</b></td><td>{v.ec_id}</td></tr>"

    return f"""
    <div style="
        font-family: 'Inter', system-ui, sans-serif;
        background: #0a0f1a;
        color: #ffffff;
        border-radius: 10px;
        padding: 14px 18px;
        min-width: 260px;
        border: 1px solid rgba(255,255,255,0.12);
    ">
        <div style="
            display: flex; align-items: center; gap: 8px;
            border-bottom: 2px solid {risk_colour};
            padding-bottom: 8px; margin-bottom: 10px;
        ">
            <span style="font-size:18px">{emoji}</span>
            <span style="font-size:14px; font-weight:500; color:{risk_colour}">
                {risk_label} RISK
            </span>
        </div>
        <table style="width:100%; font-size:12px; border-collapse:collapse;">
            <tr>
                <td style="padding:3px 0; color:rgba(255,255,255,0.65)"><b>ID</b></td>
                <td style="padding:3px 0; color:#fff">{d.detection_id}</td>
            </tr>
            <tr>
                <td><b>Area</b></td>
                <td>{d.area_ha:.1f} ha</td>
            </tr>
            <tr>
                <td><b>Mining Score</b></td>
                <td>{d.mining_score:.3f} / 1.0</td>
            </tr>
            <tr>
                <td><b>Risk Score</b></td>
                <td style="color:{risk_colour}">{v.risk_score:.0f} / 100</td>
            </tr>
            <tr>
                <td><b>Location</b></td>
                <td>{d.lat:.5f}°N, {d.lon:.5f}°E</td>
            </tr>
            <tr>
                <td><b>Lease Status</b></td>
                <td>{v.lease_status.value if v else 'Unknown'}</td>
            </tr>
            {ec_row}
            <tr>
                <td><b>Land Type</b></td>
                <td>{v.land_type or 'Unknown' if v else 'Unknown'}</td>
            </tr>
            {alert_row}
        </table>
    </div>
    """


# ---------------------------------------------------------------------------
# Lease boundary layer
# ---------------------------------------------------------------------------

def _add_lease_layer(fmap: folium.Map) -> None:
    """Add lease boundary polygons as a named layer."""
    lease_path = Path("config/lease_boundaries/jharkhand_sample.geojson")
    if not lease_path.exists():
        logger.warning("Lease boundary file not found — skipping layer.")
        return

    with open(lease_path) as f:
        leases = json.load(f)

    layer = folium.FeatureGroup(name="Mining Leases", show=True)
    for feature in leases.get("features", []):
        props = feature.get("properties", {})
        status = props.get("status", "UNKNOWN")
        fill_colour = "#FF9933" if status == "ACTIVE" else "#888888"

        popup_html = f"""
        <div style="font-family:Inter,sans-serif; background:#0a0f1a; color:#fff;
                    padding:10px; border-radius:8px; min-width:180px;">
            <b>{props.get('mine_name', 'Unknown Mine')}</b><br/>
            <span style="color:rgba(255,255,255,0.65)">{props.get('company', '')}</span><br/>
            <span style="margin-top:6px; display:block">
                Status: <b style="color:{'#00C853' if status=='ACTIVE' else '#FF4444'}">{status}</b>
            </span>
            <span>Commodity: {props.get('commodity', 'N/A')}</span><br/>
            <span>Area: {props.get('area_ha', 'N/A')} ha</span>
        </div>
        """

        folium.GeoJson(
            feature,
            style_function=lambda f, fc=fill_colour: {
                "fillColor": fc,
                "color": "#FF9933",
                "weight": 1.5,
                "fillOpacity": 0.18,
                "opacity": 0.7,
            },
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=props.get("mine_name", "Mining Lease"),
        ).add_to(layer)

    layer.add_to(fmap)
    logger.debug("Lease boundary layer added ({} features).", len(leases.get("features", [])))


# ---------------------------------------------------------------------------
# Detection marker layer
# ---------------------------------------------------------------------------

def _add_detection_layer(
    fmap: folium.Map,
    detections: list[DetectionResult],
    verifications: list[VerificationResult],
    alerts: list[AlertRecord],
) -> None:
    """Add detection markers, colour-coded by risk level."""
    # Build lookup dicts
    verify_map = {v.detection_id: v for v in verifications}
    alert_map  = {a.detection_id: a for a in alerts}

    illegal_layer = folium.FeatureGroup(name="⚠ Illegal Mining", show=True)
    legal_layer   = folium.FeatureGroup(name="✓ Legal Activity", show=True)

    for d in detections:
        v = verify_map.get(d.detection_id)
        a = alert_map.get(d.detection_id)

        colour       = _RISK_COLOUR.get(v.risk_level if v else RiskLevel.LOW, "#FFFFFF")
        is_illegal   = v.is_illegal if v else False
        radius       = max(8, min(24, int(d.area_ha / 2)))  # size proportional to area
        popup_html   = _build_popup(d, v, a)

        marker = folium.CircleMarker(
            location=[d.lat, d.lon],
            radius=radius,
            color=colour,
            weight=2,
            fill=True,
            fill_color=colour,
            fill_opacity=0.55,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{_RISK_EMOJI.get(v.risk_level if v else RiskLevel.LOW)} "
                    f"{d.detection_id} | {v.risk_level.value if v else 'N/A'} | {d.area_ha:.1f}ha",
        )

        if is_illegal:
            marker.add_to(illegal_layer)
        else:
            marker.add_to(legal_layer)

    illegal_layer.add_to(fmap)
    legal_layer.add_to(fmap)


# ---------------------------------------------------------------------------
# Heatmap layer (optional — shows mining intensity)
# ---------------------------------------------------------------------------

def _add_heatmap_layer(fmap: folium.Map, detections: list[DetectionResult]) -> None:
    """Add a heatmap layer showing mining score intensity."""
    heat_data = [
        [d.lat, d.lon, d.mining_score]
        for d in detections
        if d.mining_score > 0
    ]
    if not heat_data:
        return

    HeatMap(
        heat_data,
        name="Mining Intensity Heatmap",
        min_opacity=0.3,
        max_zoom=15,
        radius=25,
        blur=20,
        gradient={0.3: "#138808", 0.6: "#FF9933", 1.0: "#FF4444"},
        show=False,  # hidden by default, user can toggle
    ).add_to(fmap)


# ---------------------------------------------------------------------------
# Main map builder
# ---------------------------------------------------------------------------

def build_map(result: PipelineResult) -> folium.Map:
    """
    Build and return a fully configured Folium map from a PipelineResult.

    Parameters
    ----------
    result : PipelineResult from the pipeline runner

    Returns
    -------
    folium.Map — ready to save as HTML
    """
    cfg = SETTINGS.get("dashboard", {})
    center     = cfg.get("map_center", [23.65, 86.0])
    zoom_start = cfg.get("map_zoom", 11)

    # Base map — dark satellite feel
    fmap = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles="CartoDB dark_matter",
        prefer_canvas=True,
    )

    # Add layers
    _add_lease_layer(fmap)
    _add_detection_layer(fmap, result.detections, result.verifications, result.alerts)
    _add_heatmap_layer(fmap, result.detections)

    # Layer control (toggle lease / detections / heatmap)
    folium.LayerControl(position="topright", collapsed=False).add_to(fmap)

    # Title overlay
    synthetic_badge = (
        '<span style="background:#FF9933;color:#0a0f1a;padding:2px 8px;'
        'border-radius:4px;font-size:10px;margin-left:8px">SYNTHETIC DATA</span>'
        if result.synthetic_mode else ""
    )
    illegal_count = sum(1 for v in result.verifications if v.is_illegal) if result.verifications else "?"
    title_html = f"""
    <div style="
        position: fixed; top: 16px; left: 16px; z-index: 9999;
        background: rgba(10,15,26,0.92);
        border: 1px solid rgba(255,255,255,0.10);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 14px 20px;
        font-family: 'Inter', system-ui, sans-serif;
        color: #fff;
    ">
        <div style="font-size:16px; font-weight:500; color:#FF9933;">
            🛰 Mining Watch — Jharkhand{synthetic_badge}
        </div>
        <div style="font-size:12px; color:rgba(255,255,255,0.65); margin-top:4px;">
            {len(result.detections)} detections &nbsp;|&nbsp;
            <span style="color:#FF4444">{illegal_count} illegal</span> &nbsp;|&nbsp;
            Run: {result.run_id}
        </div>
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(title_html))

    logger.success(
        "Folium map built | {} detections | {} lease polygons",
        len(result.detections),
        4,  # from jharkhand_sample.geojson
    )
    return fmap


__all__ = ["build_map"]
