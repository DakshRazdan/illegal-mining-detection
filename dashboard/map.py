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
    RiskLevel.CRITICAL: "#FF0000",   # keep red but opaque
    RiskLevel.HIGH:     "#FF6600",   # orange
    RiskLevel.MEDIUM:   "#CC8800",   # darker yellow for light background
    RiskLevel.LOW:      "#228B22",   # dark green
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
                "color": "#8B4513",
                "weight": 2.0,
                "fillOpacity": 0.15,
                "opacity": 0.8,
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
            fill_opacity=0.9,
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
        gradient={ 0.2: '#FF9933', 0.5: '#FF4400', 0.8: '#CC0000', 1.0: '#660000' },
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

    # Base map — Esri satellite imagery
    fmap = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community",
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
        '<span style="background: #FF9933; color: #0a0f1a; font-size: 11px; padding: 2px 8px; border-radius: 4px; margin-left:8px">SYNTHETIC DATA</span>'
        if result.synthetic_mode else ""
    )
    illegal_count = sum(1 for v in result.verifications if v.is_illegal) if result.verifications else "?"
    title_html = f"""
    <div style="
        position: fixed; top: 16px; left: 0px; z-index: 9999;
        background: rgba(10, 15, 26, 0.9);
        border: none;
        border-left: 3px solid #FF9933;
        border-radius: 0 12px 12px 0;
        padding: 12px 20px;
        font-family: 'Inter', system-ui, sans-serif;
        color: #fff;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        user-select: none;
        -webkit-user-select: none;
    ">
        <div style="font-size:16px; font-weight:500; color:#FF9933;">
            Mining Watch — Jharkhand{synthetic_badge}
        </div>
        <div style="font-size:13px; color:rgba(255,255,255,0.7); margin-top:4px;">
            {len(result.detections)} detections &nbsp;|&nbsp;
            <span style="color:#FF4444">{illegal_count} illegal</span> &nbsp;|&nbsp;
            Run: {result.run_id}
        </div>
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(title_html))
    
    # Legend Overlay
    legend_html = """
    <div style="
        position: fixed; bottom: 30px; right: 30px; z-index: 9999;
        background: rgba(10, 15, 26, 0.85);
        border: 1px solid rgba(255, 153, 51, 0.4);
        border-radius: 12px;
        padding: 12px 16px;
        color: white;
        font-family: Inter, system-ui;
        font-size: 13px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    ">
        <div style="margin-bottom:6px; display:flex; align-items:center;">
            <span style="display:inline-block;width:12px;height:12px;background:#FF4444;margin-right:8px;border-radius:2px;"></span> Illegal Mining (CRITICAL)
        </div>
        <div style="margin-bottom:6px; display:flex; align-items:center;">
            <span style="display:inline-block;width:12px;height:12px;background:#FF9933;margin-right:8px;border-radius:2px;"></span> Illegal Mining (HIGH)
        </div>
        <div style="margin-bottom:6px; display:flex; align-items:center;">
            <span style="display:inline-block;width:12px;height:12px;background:#FFD700;margin-right:8px;border-radius:2px;"></span> Suspicious (MEDIUM)
        </div>
        <div style="margin-bottom:6px; display:flex; align-items:center;">
            <span style="display:inline-block;width:12px;height:12px;background:#00C853;margin-right:8px;border-radius:2px;"></span> Legal Activity
        </div>
        <div style="display:flex; align-items:center;">
            <span style="display:inline-block;width:12px;height:12px;border:2px solid #FF9933;margin-right:8px;background:rgba(255,153,51,0.2);"></span> Mining Lease Boundary
        </div>
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))

    # Temporal Scanner UI Overlay & Controller JS
    temporal_html = """
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <!-- Temporal Slider UI -->
    <div id="temporal-panel" style="
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        width: 800px; max-width: 90vw; z-index: 9999;
        background: rgba(10, 15, 26, 0.9);
        border: 1px solid rgba(255, 153, 51, 0.3);
        border-radius: 16px;
        padding: 24px;
        color: white;
        font-family: 'Inter', system-ui, sans-serif;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        backdrop-filter: blur(10px);
    ">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 16px;">
            <div>
                <h3 style="margin:0 0 4px 0; font-size:16px; font-weight:600; color:#fff;">Vegetation Change Over Time — Jharkhand Mining Belt</h3>
                <p style="margin:0; font-size:12px; color:rgba(255,255,255,0.6);">Sentinel-2 NDVI | Microsoft Planetary Computer | 2019–2024</p>
            </div>
            
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:12px; color:#aaa;">Opacity:</span>
                <input type="range" id="temporal-opacity" min="0" max="1" step="0.1" value="0.65" style="width:80px; accent-color:#FF9933">
            </div>
        </div>

        <div style="display:flex; align-items:center; gap: 16px; margin-bottom: 12px;">
            <button onclick="tempPrev()" style="background:transparent; border:1px solid rgba(255,255,255,0.2); color:#fff; border-radius:6px; padding:6px 12px; cursor:pointer;">◀◀</button>
            <button id="temp-play-btn" onclick="togglePlay()" style="background:#FF9933; border:none; color:#0a0f1a; border-radius:6px; padding:6px 20px; font-weight:600; cursor:pointer; min-width:80px;">PLAY</button>
            <button onclick="tempNext()" style="background:transparent; border:1px solid rgba(255,255,255,0.2); color:#fff; border-radius:6px; padding:6px 12px; cursor:pointer;">▶▶</button>
            
            <input type="range" id="temporal-slider" min="0" max="11" step="1" value="0" style="flex:1; accent-color:#FF9933;">
        </div>

        <div style="display:flex; justify-content:space-between; font-family:monospace; font-size:12px; color:#aaa; margin-bottom: 16px;">
            <span id="ts-start-label">Q1 2019</span>
            <span id="ts-end-label">Q3 2024</span>
        </div>

        <div id="ts-stats-line" style="font-size:13px; color:rgba(255,255,255,0.8); margin-bottom:12px; text-align:center; font-weight:500;">
            Loading temporal metadata...
        </div>

        <div style="height: 60px; width: 100%;">
            <canvas id="ndviChart"></canvas>
        </div>
    </div>

    <!-- Initialization / Logic -->
    <script>
    // Folium assigns the map to a variable we can find via class
    window.addEventListener('load', function() {
        // Find the map object dynamically since Folium names it map_xxxx
        let foliumMap = null;
        for (let key in window) {
            if (key.startsWith('map_') && window[key] instanceof L.Map) {
                foliumMap = window[key];
                break;
            }
        }

        const state = {
            periods: [],
            currentIndex: 0,
            isPlaying: false,
            playInterval: null,
            overlayLayer: null,
            aoiBounds: [[23.5, 85.8], [23.8, 86.2]], // Leaflet uses [lat, lon]
            chart: null
        };

        const ui = {
            slider: document.getElementById('temporal-slider'),
            opacity: document.getElementById('temporal-opacity'),
            playBtn: document.getElementById('temp-play-btn'),
            stats: document.getElementById('ts-stats-line')
        };

        const ctx = document.getElementById('ndviChart').getContext('2d');
        state.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'NDVI Mean',
                    data: [],
                    borderColor: '#FF9933',
                    backgroundColor: 'rgba(255,153,51,0.15)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointBackgroundColor: '#0a0f1a',
                    pointBorderColor: '#FF9933'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                    x: { display: false },
                    y: { 
                        display: true, 
                        min: 0, 
                        max: 0.6,
                        ticks: { color: 'rgba(255,255,255,0.4)', font: {size: 10}, stepSize: 0.2 },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    }
                }
            }
        });

        async function initTemporal() {
            try {
                const res = await fetch('/api/temporal/periods');
                const data = await res.json();
                state.periods = data.periods;
                
                ui.slider.max = state.periods.length - 1;
                document.getElementById('ts-start-label').innerText = state.periods[0].label;
                document.getElementById('ts-end-label').innerText = state.periods[state.periods.length-1].label;
                
                state.chart.data.labels = state.periods.map(p => p.label);
                state.chart.data.datasets[0].data = state.periods.map(p => p.ndvi_mean || 0);
                state.chart.update();

                loadFrame(0);
            } catch (err) {
                ui.stats.innerText = "Error loading temporal metadata. Is backend running?";
            }
        }

        window.loadFrame = async function(index) {
            ui.stats.innerText = `Loading ${state.periods[index].label}...`;
            try {
                const res = await fetch(`/api/temporal/frame/${index}`);
                const frame = await res.json();
                
                if (frame.status === 'ok' && frame.ndvi_png_b64) {
                    const imgUrl = `data:image/png;base64,${frame.ndvi_png_b64}`;
                    
                    if (state.overlayLayer && foliumMap) {
                        foliumMap.removeLayer(state.overlayLayer);
                    }
                    
                    if (foliumMap) {
                        state.overlayLayer = L.imageOverlay(imgUrl, state.aoiBounds, {
                            opacity: parseFloat(ui.opacity.value),
                            interactive: false,
                            zIndex: 200 // explicitly below Folium heatmaps/markers
                        }).addTo(foliumMap);
                    }
                    
                    state.currentIndex = index;
                    ui.slider.value = index;
                    ui.stats.innerHTML = `<span style="color:#FF9933">${frame.label}</span> &nbsp;|&nbsp; Scene: ${frame.scene_date || 'N/A'} &nbsp;|&nbsp; Cloud: ${(frame.cloud_cover||0).toFixed(1)}% &nbsp;|&nbsp; NDVI Mean: ${(frame.ndvi_mean||0).toFixed(3)}`;
                    
                    state.chart.data.datasets[0].pointBackgroundColor = state.periods.map((_, i) => i === index ? '#FF9933' : '#0a0f1a');
                    state.chart.data.datasets[0].pointRadius = state.periods.map((_, i) => i === index ? 6 : 4);
                    state.chart.update();

                } else {
                    ui.stats.innerHTML = `<span style="color:#FF9933">${state.periods[index].label}</span> &nbsp;|&nbsp; <span style="color:#FF0000">No precise cloud-free scenes</span>`;
                    state.currentIndex = index;
                    ui.slider.value = index;
                }
            } catch (err) {
                ui.stats.innerText = "Error loading frame overlay.";
            }
        };

        window.togglePlay = function() {
            if (state.isPlaying) {
                clearInterval(state.playInterval);
                state.isPlaying = false;
                ui.playBtn.innerText = "PLAY";
            } else {
                state.isPlaying = true;
                ui.playBtn.innerText = "PAUSE";
                state.playInterval = setInterval(() => {
                    let next = state.currentIndex + 1;
                    if (next >= state.periods.length) next = 0;
                    loadFrame(next);
                }, 2000);
            }
        };

        window.tempNext = function() {
            if (state.isPlaying) togglePlay();
            let next = state.currentIndex + 1;
            if (next >= state.periods.length) next = 0;
            loadFrame(next);
        }

        window.tempPrev = function() {
            if (state.isPlaying) togglePlay();
            let prev = state.currentIndex - 1;
            if (prev < 0) prev = state.periods.length - 1;
            loadFrame(prev);
        }

        ui.slider.addEventListener('input', (e) => {
            if (state.isPlaying) togglePlay();
            loadFrame(parseInt(e.target.value));
        });

        ui.opacity.addEventListener('input', (e) => {
            if (state.overlayLayer) {
                state.overlayLayer.setOpacity(parseFloat(e.target.value));
            }
        });

        initTemporal();
    });
    </script>
    """
    fmap.get_root().html.add_child(folium.Element(temporal_html))

    logger.success(
        "Folium map built | {} detections | {} lease polygons",
        len(result.detections),
        4,  # from jharkhand_sample.geojson
    )
    return fmap


__all__ = ["build_map"]
