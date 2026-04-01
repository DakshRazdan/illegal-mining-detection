"""
src/dispatch/colab_bridge.py — In-memory store for Colab-ingested numpy arrays.

Receives the mining_score, NDVI, BSI, NDWI, NBR arrays computed in the
Colab notebook and makes them available to all API endpoints.

Flow:
    Colab notebook
        → POST /api/colab/ingest  (multipart .npz upload)
        → ingest_npz()            (writes to _STORE)
        → mining_endpoints.py     (reads _STORE, renders PNG overlays)
        → script.js               (displays overlays on Leaflet map)
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

import numpy as np

logger = logging.getLogger("colab_bridge")

# ── COLORMAPS per index ────────────────────────────────────────────────────
_INDEX_CMAPS = {
    "ndvi":      ("RdYlGn",   -0.3, 0.8),
    "bsi":       ("OrRd",      0.0, 0.6),
    "ndwi":      ("RdBu",     -0.5, 0.5),
    "turbidity": ("YlOrBr",    0.0, 0.5),
    "mining":    ("YlOrRd",    0.0, 1.0),
    "rgb":       (None,        None, None),
}

# ── In-memory store ────────────────────────────────────────────────────────
_STORE: dict[str, Any] = {
    # 2-D numpy arrays (h × w), keyed as "ndvi_a", "ndvi_b", etc.
    "ndvi_a":         None,
    "ndvi_b":         None,
    "bsi_a":          None,
    "bsi_b":          None,
    "ndwi_a":         None,
    "ndwi_b":         None,
    "nbr_a":          None,
    "nbr_b":          None,
    "mining_score":   None,   # 4-index fused (original)
    "mining_score_v2": None,  # 6-index fused (extended bands)

    # Temporal series (list[float]) — one value per year, 2019-2023
    "temporal_dates":  [],    # list[str]  e.g. ["2019", "2020", …]
    "temporal_scores": [],    # list[float] mean mining score per year

    # Land-cover cluster labels (h × w int array)
    "labels_a": None,
    "labels_b": None,

    # Scalar stats
    "affected_area_ha": None,
    "critical_area_ha": None,
    "peak_score":       None,

    # AOI bounds — [[lat_min, lon_min], [lat_max, lon_max]]
    "aoi_bounds": [[23.5, 85.8], [23.8, 86.2]],

    # Whether real data has been loaded
    "loaded": False,
}


# ── Ingest ─────────────────────────────────────────────────────────────────

def ingest_npz(npz_bytes: bytes) -> dict[str, Any]:
    """
    Load a .npz file produced by the Colab notebook.

    Expected keys (all optional but at least one must be present):
        ndvi_a, ndvi_b, bsi_a, bsi_b, ndwi_a, ndwi_b,
        nbr_a, nbr_b, mining_score, mining_score_v2,
        temporal_dates, temporal_scores,
        labels_a, labels_b,
        affected_area_ha, critical_area_ha, peak_score
    """
    try:
        buf = io.BytesIO(npz_bytes)
        data = np.load(buf, allow_pickle=True)
    except Exception as exc:
        raise ValueError(f"Cannot read .npz file: {exc}") from exc

    loaded_keys = []
    for key in _STORE:
        if key in data:
            val = data[key]
            # numpy scalars → Python float
            if val.ndim == 0:
                _STORE[key] = float(val)
            # 1-D arrays of strings → list[str]
            elif val.ndim == 1 and val.dtype.kind in ("U", "S", "O"):
                _STORE[key] = val.tolist()
            # 1-D float arrays → list[float]
            elif val.ndim == 1:
                _STORE[key] = val.tolist()
            else:
                _STORE[key] = val.astype(np.float32) if val.dtype.kind == "f" else val
            loaded_keys.append(key)

    _STORE["loaded"] = len(loaded_keys) > 0
    logger.info("Colab bridge: loaded keys=%s", loaded_keys)

    return {
        "loaded_keys": loaded_keys,
        "shape": _get_shape(),
        "loaded": _STORE["loaded"],
    }


def is_loaded() -> bool:
    return _STORE["loaded"]


def get_store() -> dict[str, Any]:
    return _STORE


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_shape() -> list[int] | None:
    for k in ("mining_score", "ndvi_a", "ndvi_b"):
        if _STORE[k] is not None:
            return list(_STORE[k].shape)
    return None


def _array_for_index(index_name: str, period: str = "a") -> np.ndarray | None:
    """
    Return the correct 2-D array for a given index name.
    period = "a" → after (2023), period = "b" → before (2019).
    """
    mapping = {
        "ndvi":      f"ndvi_{period}",
        "bsi":       f"bsi_{period}",
        "ndwi":      f"ndwi_{period}",
        "turbidity": f"ndwi_{period}",   # use NDWI as turbidity proxy
        "mining":    "mining_score_v2" if _STORE["mining_score_v2"] is not None else "mining_score",
    }
    key = mapping.get(index_name)
    if key is None:
        return None
    return _STORE.get(key)


def array_to_png_b64(
    arr: np.ndarray,
    cmap: str = "RdYlGn",
    vmin: float | None = None,
    vmax: float | None = None,
    mask_below: float | None = None,
) -> str:
    """
    Convert a 2-D numpy array to a transparent-background PNG (base64).
    Used for Leaflet imageOverlay.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors

        arr = np.nan_to_num(arr.astype(float), nan=0.0)

        if mask_below is not None:
            arr = np.ma.masked_where(arr < mask_below, arr)

        fig, ax = plt.subplots(figsize=(6, 5), dpi=120)
        fig.patch.set_alpha(0.0)
        ax.set_facecolor("none")
        ax.imshow(arr, cmap=cmap, vmin=vmin, vmax=vmax,
                  interpolation="bilinear", origin="upper")
        ax.axis("off")
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight",
                    pad_inches=0, transparent=True, dpi=120)
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")

    except Exception as exc:
        logger.error("PNG render failed: %s", exc)
        return ""


def render_index_png(index_name: str, period_idx: int = 11) -> str | None:
    """
    Render any index as a PNG overlay for the given time period index.

    period_idx 0–5  → "before" data (2019)
    period_idx 6–11 → "after"  data (2023)

    Returns base64 PNG string or None if data unavailable.
    """
    period = "b" if period_idx < 6 else "a"
    arr = _array_for_index(index_name, period)
    if arr is None:
        return None

    cmap, vmin, vmax = _INDEX_CMAPS.get(index_name, ("viridis", None, None))
    mask_below = 0.2 if index_name == "mining" else None

    return array_to_png_b64(arr, cmap=cmap, vmin=vmin, vmax=vmax,
                             mask_below=mask_below)


# ── Temporal data helpers ──────────────────────────────────────────────────

def get_temporal_periods() -> list[dict]:
    """
    Return period metadata for the temporal slider.
    Falls back to synthetic yearly data if nothing ingested.
    """
    dates  = _STORE["temporal_dates"]
    scores = _STORE["temporal_scores"]

    if dates and scores and len(dates) == len(scores):
        return [
            {
                "index":     i,
                "label":     str(dates[i]),
                "ndvi_mean": round(float(scores[i]), 4),
                "status":    "ok",
            }
            for i in range(len(dates))
        ]

    # Fallback: 12 synthetic quarters (Jan 2022 – Dec 2024)
    fallback_labels = [
        "Jan 2022", "Mar 2022", "Jun 2022", "Sep 2022",
        "Dec 2022", "Mar 2023", "Jun 2023", "Sep 2023",
        "Dec 2023", "Mar 2024", "Sep 2024", "Dec 2024",
    ]
    fallback_ndvi = [
        0.62, 0.60, 0.57, 0.55, 0.52, 0.50,
        0.47, 0.44, 0.42, 0.39, 0.37, 0.35,
    ]
    return [
        {"index": i, "label": lbl, "ndvi_mean": fallback_ndvi[i], "status": "synthetic"}
        for i, lbl in enumerate(fallback_labels)
    ]


def get_temporal_frame(index: int) -> dict:
    """
    Return a single temporal frame: PNG overlays + metadata.
    Renders from stored arrays — no Planetary Computer call.
    """
    periods = get_temporal_periods()
    if index < 0 or index >= len(periods):
        return {"error": "Index out of range"}

    period_meta = periods[index]

    frame: dict[str, Any] = {
        "index":      index,
        "label":      period_meta["label"],
        "ndvi_mean":  period_meta.get("ndvi_mean"),
        "status":     "ok" if _STORE["loaded"] else "synthetic",
    }

    if _STORE["loaded"]:
        for idx_name in ("ndvi", "bsi", "ndwi", "turbidity", "mining"):
            png = render_index_png(idx_name, period_idx=index)
            if png:
                frame[f"{idx_name}_png_b64"] = png
    # surface the primary ndvi overlay regardless of key name
    if "ndvi_png_b64" not in frame and _STORE["loaded"]:
        frame["ndvi_png_b64"] = frame.get("ndvi_png_b64", "")

    return frame


# ── Hotspot extraction ─────────────────────────────────────────────────────

def get_hotspot_geojson(threshold: float = 0.55) -> dict:
    """
    Convert mining_score array into a GeoJSON FeatureCollection of hotspot
    point features. Coordinates derived from AOI bounds.
    """
    score_arr = _STORE.get("mining_score_v2") or _STORE.get("mining_score")
    if score_arr is None:
        return {"type": "FeatureCollection", "features": []}

    bounds = _STORE["aoi_bounds"]   # [[lat_min, lon_min], [lat_max, lon_max]]
    lat_min, lon_min = bounds[0]
    lat_max, lon_max = bounds[1]
    h, w = score_arr.shape

    # Find local maxima above threshold using block sampling
    features = []
    block = max(1, h // 20)   # ~20 rows of blocks
    for r in range(0, h, block):
        for c in range(0, w, block):
            patch = score_arr[r:r+block, c:c+block]
            peak  = float(np.nanmax(patch)) if patch.size else 0.0
            if peak < threshold:
                continue
            # Pixel → geographic coordinate
            rr, cc = np.unravel_index(np.nanargmax(patch), patch.shape)
            pr, pc = r + rr, c + cc
            lat = lat_max - (pr / h) * (lat_max - lat_min)
            lon = lon_min + (pc / w) * (lon_max - lon_min)
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "disturbance": round(peak, 4),
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "scene_date": "2023",
                    "period": "2019-2023",
                },
            })

    high_risk = [f for f in features if f["properties"]["disturbance"] > 0.75]
    total = len(features)

    return {
        "type": "FeatureCollection",
        "features": features,
        "stats": {
            "n_hotspots":     total,
            "high_risk_count": len(high_risk),
            "high_risk_pct":  round(len(high_risk) / total * 100) if total else 0,
            "threshold":      threshold,
            "source":         "colab_ingest" if _STORE["loaded"] else "synthetic",
        },
    }


# ── Mining stats timeline ──────────────────────────────────────────────────

def get_mining_stats_timeline() -> dict:
    """
    Return timeline + summary stats for /api/mining/stats.
    Used by script.js refreshData() to update right-panel charts.
    """
    dates  = _STORE["temporal_dates"]
    scores = _STORE["temporal_scores"]

    if dates and scores and len(dates) == len(scores):
        timeline = [
            {
                "period":       str(dates[i]),
                "ndvi_mean":    None,   # not stored per-year in Colab output
                "bsi_mean":     None,
                "mining_mean":  round(float(scores[i]), 4),
            }
            for i in range(len(dates))
        ]
        latest  = float(scores[-1]) if scores else 0.0
        ok_pds  = len(scores)
    else:
        # No real data — return empty timeline
        timeline = []
        latest   = 0.0
        ok_pds   = 0

    return {
        "timeline": timeline,
        "summary": {
            "latest_mining": round(latest, 4),
            "ok_periods":    ok_pds,
            "affected_ha":   _STORE.get("affected_area_ha"),
            "critical_ha":   _STORE.get("critical_area_ha"),
            "peak_score":    _STORE.get("peak_score"),
            "source":        "colab_ingest" if _STORE["loaded"] else "synthetic",
        },
    }