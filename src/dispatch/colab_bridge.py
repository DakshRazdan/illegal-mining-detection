"""
src/dispatch/colab_bridge.py
Bridge between Colab-computed numpy arrays and the live dashboard API.

When Colab uploads a .npz via POST /api/colab/ingest:
  1. Arrays are stored in memory (_STORE)
  2. Mining hotspots are extracted from real pixel blobs (not hardcoded)
  3. PNG overlays are rendered from real index arrays
  4. Temporal periods are built from real yearly scores

This replaces ALL hardcoded dots on the map with real detections.
"""

from __future__ import annotations

import io
import base64
import uuid
from datetime import datetime
from typing import Optional

import numpy as np
from loguru import logger

# ── In-memory store ───────────────────────────────────────────────────────────
_STORE: dict = {
    "loaded":            False,
    "ndvi_a":            None,   # NDVI after  (H×W float32)
    "ndvi_b":            None,   # NDVI before (H×W float32)
    "bsi_a":             None,
    "bsi_b":             None,
    "ndwi_a":            None,
    "ndwi_b":            None,
    "nbr_a":             None,
    "nbr_b":             None,
    "mining_score":      None,   # 4-index fused map
    "mining_score_v2":   None,   # 6-index fused map (preferred)
    "mining_filtered":   None,   # after FP filter
    "labels_a":          None,   # K-Means clusters after
    "labels_b":          None,   # K-Means clusters before
    "temporal_dates":    None,   # 1-D string array ["2019","2020",...]
    "temporal_scores":   None,   # 1-D float array
    "affected_area_ha":  None,
    "critical_area_ha":  None,
    "peak_score":        None,
    "aoi_bounds":        [85.8, 23.5, 86.2, 23.8],  # default Jharkhand
    "shape":             None,
    "ingested_at":       None,
}

EXPECTED_KEYS = [
    "ndvi_a","ndvi_b","bsi_a","bsi_b","ndwi_a","ndwi_b",
    "nbr_a","nbr_b","mining_score","mining_score_v2",
    "mining_filtered","labels_a","labels_b",
    "temporal_dates","temporal_scores",
    "affected_area_ha","critical_area_ha","peak_score",
]


# ── Ingest ────────────────────────────────────────────────────────────────────

def ingest_npz(raw_bytes: bytes) -> dict:
    """
    Load a .npz file from Colab into memory.
    Returns summary dict with loaded_keys and shape.
    """
    global _STORE

    try:
        npz = np.load(io.BytesIO(raw_bytes), allow_pickle=True)
    except Exception as e:
        raise ValueError(f"Failed to parse .npz: {e}")

    loaded_keys = []
    shape = None

    for key in EXPECTED_KEYS:
        if key in npz:
            val = npz[key]
            # Convert 0-d arrays to scalars
            if val.ndim == 0:
                _STORE[key] = float(val)
            else:
                _STORE[key] = val.astype(float) if val.dtype.kind in ('f','i','u') else val
            loaded_keys.append(key)
            if val.ndim == 2 and shape is None:
                shape = list(val.shape)

    if not loaded_keys:
        raise ValueError("No recognised arrays found in .npz. Check key names.")

    # Optional: aoi_bounds override
    if "aoi_bounds" in npz:
        _STORE["aoi_bounds"] = npz["aoi_bounds"].tolist()

    _STORE["loaded"]      = True
    _STORE["shape"]       = shape
    _STORE["ingested_at"] = datetime.utcnow().isoformat() + "Z"

    logger.success("Colab bridge: ingested {} keys, shape={}", len(loaded_keys), shape)
    return {"loaded_keys": loaded_keys, "shape": shape}


def is_loaded() -> bool:
    return bool(_STORE.get("loaded"))


def get_store() -> dict:
    return _STORE


# ── Best mining score ─────────────────────────────────────────────────────────

def _best_score() -> Optional[np.ndarray]:
    """Return the best available mining probability map."""
    for key in ("mining_score_v2", "mining_filtered", "mining_score"):
        val = _STORE.get(key)
        if val is not None and isinstance(val, np.ndarray):
            return val.astype(float)
    return None


# ── PNG rendering ─────────────────────────────────────────────────────────────

def _array_to_png_b64(arr: np.ndarray, cmap_name: str, vmin: float, vmax: float) -> str:
    """Convert numpy array to base64 PNG via matplotlib colormap."""
    from matplotlib import cm
    from PIL import Image

    arr = np.nan_to_num(arr, nan=0.0)
    arr = np.clip((arr - vmin) / (vmax - vmin + 1e-10), 0, 1)
    rgb = (cm.get_cmap(cmap_name)(arr)[:, :, :3] * 255).astype(np.uint8)
    img = Image.fromarray(rgb).resize((256, 256))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _compute_delta_png(before: Optional[np.ndarray], after: Optional[np.ndarray],
                        cmap: str, direction: str = "loss") -> Optional[str]:
    """
    Compute before→after delta and render as PNG.
    direction='loss'  → before - after (vegetation loss, water loss)
    direction='gain'  → after - before (bare soil gain)
    """
    if before is None or after is None:
        return None
    delta = (before - after) if direction == "loss" else (after - before)
    delta = np.clip(delta, 0, None)   # only positive change
    return _array_to_png_b64(delta, cmap, 0, delta.max() if delta.max() > 0 else 1)


def render_frame_pngs(index: int) -> dict:
    """
    Render all 5 index PNGs for a given temporal frame.
    Uses real Colab arrays scaled by temporal position.
    """
    score = _best_score()
    ndvi_a = _STORE.get("ndvi_a")
    ndvi_b = _STORE.get("ndvi_b")
    bsi_a  = _STORE.get("bsi_a")
    bsi_b  = _STORE.get("bsi_b")
    ndwi_a = _STORE.get("ndwi_a")
    ndwi_b = _STORE.get("ndwi_b")

    # Temporal interpolation: blend between before and after based on slider
    n = 12
    t = index / max(n - 1, 1)   # 0.0 = earliest, 1.0 = latest

    def blend(b, a):
        if b is None or a is None:
            return a or b
        return b * (1 - t) + a * t

    ndvi_t = blend(ndvi_b, ndvi_a)
    bsi_t  = blend(bsi_b,  bsi_a)
    ndwi_t = blend(ndwi_b, ndwi_a)

    # Mining score scaled by time (intensity grows toward present)
    mining_t = score * (0.3 + 0.7 * t) if score is not None else None

    pngs = {}
    if ndvi_t is not None:
        pngs["ndvi_png_b64"]      = _array_to_png_b64(ndvi_t, "RdYlGn", -0.2, 0.8)
    if bsi_t is not None:
        pngs["bsi_png_b64"]       = _array_to_png_b64(bsi_t,  "YlOrBr", -0.3, 0.5)
    if ndwi_t is not None:
        pngs["ndwi_png_b64"]      = _array_to_png_b64(ndwi_t, "Blues",  -0.5, 0.5)

    # Turbidity from NDVI loss (proxy — red where veg decreased)
    if ndvi_b is not None and ndvi_a is not None:
        turb = np.clip(ndvi_b - ndvi_t, 0, None)
        pngs["turbidity_png_b64"] = _array_to_png_b64(turb,   "PuRd",   0.0, 0.4)

    if mining_t is not None:
        pngs["mining_png_b64"]    = _array_to_png_b64(mining_t, "hot_r", 0.0, 1.0)

    return pngs


# ── Hotspot extraction (replaces hardcoded REGION_SITES) ─────────────────────

def extract_hotspots(
    threshold:      float = 0.35,
    max_hotspots:   int   = 200,
    aoi_bounds:     list  = None,
) -> list[dict]:
    """
    Extract real mining hotspot coordinates from the Colab-computed
    mining probability map using connected-component labelling.

    Returns list of detection dicts with real lat/lon coordinates.
    This REPLACES the hardcoded REGION_SITES in script.js.
    """
    from scipy.ndimage import label as scipy_label, gaussian_filter

    score = _best_score()
    if score is None:
        return []

    bounds = aoi_bounds or _STORE.get("aoi_bounds") or [85.8, 23.5, 86.2, 23.8]
    min_lon, min_lat, max_lon, max_lat = bounds
    H, W = score.shape

    # Load illegal/legal masks if available
    mining_filtered = _STORE.get("mining_filtered")
    use_filtered    = mining_filtered is not None and isinstance(mining_filtered, np.ndarray)
    base_map        = mining_filtered.astype(float) if use_filtered else score

    # Gaussian smoothing
    try:
        base_map = gaussian_filter(base_map, sigma=1.5)
    except Exception:
        pass

    mask = base_map >= threshold
    labeled, n = scipy_label(mask)

    if n == 0:
        return []

    # Load known-mine mask from OSM geojson for legal/illegal classification
    mine_mask = _load_mine_mask(bounds, (H, W))

    detections = []
    for i in range(1, n + 1):
        blob    = labeled == i
        n_px    = int(blob.sum())
        area_ha = n_px * 0.36   # 60m pixel = 0.36 ha

        if area_ha < 0.5:
            continue

        rows, cols = np.where(blob)
        cy = float(np.mean(rows))
        cx = float(np.mean(cols))

        lon = min_lon + (cx / W) * (max_lon - min_lon)
        lat = max_lat - (cy / H) * (max_lat - min_lat)

        mean_score = float(np.mean(base_map[blob]))

        # Check if inside known mine zone
        # ── Stricter classification ─────────────────────────────────────────
        # Check centroid AND majority of blob pixels against mine mask
        if mine_mask is not None:
            blob_pixels_in_mine = int(mine_mask[rows, cols].sum())
            pct_in_mine = blob_pixels_in_mine / max(n_px, 1)
            # Only APPROVED if >60% of the blob overlaps a known mine zone
            is_inside_mine = pct_in_mine > 0.60
        else:
            is_inside_mine = False

        # Three-tier classification:
        # APPROVED  : majority overlap with known lease + any score
        # ILLEGAL   : outside known lease + high confidence (score > 0.55)
        # SUSPECTED : outside known lease + lower confidence (0.35–0.55)
        if is_inside_mine:
            status = "approved"
        elif mean_score > 0.55:
            status = "illegal"
        else:
            status = "suspected"

        # Risk formula — stricter penalties
        base_risk = mean_score * 100
        if status == "illegal":
            # Outside lease + high score → heavy penalty
            risk = base_risk + 40 + (area_ha / 10)   # larger area = higher risk
        elif status == "suspected":
            # Outside lease + moderate score → moderate penalty
            risk = base_risk + 20
        else:
            # Inside approved zone — no penalty, but still flag large expansions
            risk = base_risk + (10 if area_ha > 200 else 0)

        risk = min(risk, 100.0)
        # Stricter thresholds: need 85+ for CRITICAL
        risk_level = "CRITICAL" if risk >= 85 else "HIGH" if risk >= 65 else "MEDIUM" if risk >= 45 else "LOW"

        detections.append({
            "lat":          round(lat, 5),
            "lon":          round(lon, 5),
            "score":        round(mean_score, 4),
            "area":         round(area_ha, 1),
            "area_ha":      round(area_ha, 1),
            "status":       status,
            "risk_score":   round(risk, 1),
            "risk_level":   risk_level,
            "district":     "—",
            "name":         f"{'Illegal' if status=='illegal' else 'Approved'} Site ({mean_score*100:.0f}%)",
            "method":       "colab_spectral_rf",
            "disturbance":  round(mean_score, 4),
        })

    # Sort by score descending
    detections.sort(key=lambda x: x["score"], reverse=True)
    logger.info("Colab bridge: extracted {} hotspots from real mining map", len(detections[:max_hotspots]))
    return detections[:max_hotspots]


def _load_mine_mask(bounds: list, shape: tuple) -> Optional[np.ndarray]:
    """Load OSM known-mine polygons as a boolean raster mask."""
    import json
    from pathlib import Path
    from scipy.ndimage import binary_dilation

    lease_path = Path("config/lease_boundaries/jharkhand.geojson")
    if not lease_path.exists():
        return None

    try:
        features = json.loads(lease_path.read_text()).get("features", [])
    except Exception:
        return None

    min_lon, min_lat, max_lon, max_lat = bounds
    H, W = shape
    mask = np.zeros((H, W), dtype=bool)

    for f in features:
        geom = f.get("geometry", {})
        if geom.get("type") == "Polygon":
            for lon, lat in geom["coordinates"][0]:
                col = int((lon - min_lon) / (max_lon - min_lon) * W)
                row = int((max_lat - lat) / (max_lat - min_lat) * H)
                if 0 <= row < H and 0 <= col < W:
                    mask[row, col] = True
        elif geom.get("type") == "Point":
            lon, lat = geom["coordinates"][0], geom["coordinates"][1]
            col = int((lon - min_lon) / (max_lon - min_lon) * W)
            row = int((max_lat - lat) / (max_lat - min_lat) * H)
            if 0 <= row < H and 0 <= col < W:
                mask[row, col] = True

    try:
        mask = binary_dilation(mask, iterations=8)
    except Exception:
        pass

    return mask


# ── Temporal periods ──────────────────────────────────────────────────────────

def get_temporal_periods() -> list[dict]:
    """
    Build temporal period list from Colab-ingested data.
    Uses real temporal_dates and temporal_scores arrays.
    Falls back to 12-quarter synthetic if not available.
    """
    dates  = _STORE.get("temporal_dates")
    scores = _STORE.get("temporal_scores")

    if dates is not None and scores is not None:
        periods = []
        for i, (d, s) in enumerate(zip(dates, scores)):
            label = str(d) if not isinstance(d, str) else d
            periods.append({
                "index":      i,
                "label":      label,
                "start":      f"{label}-01-01" if len(label) == 4 else label,
                "end":        f"{label}-12-31" if len(label) == 4 else label,
                "scene_date": f"{label}-06-01" if len(label) == 4 else None,
                "ndvi_mean":  float(s),
                "status":     "ok",
            })
        return periods

    # Synthetic fallback
    quarters = [
        ("2019-01-01","2019-03-31","Q1 2019"),
        ("2019-07-01","2019-09-30","Q3 2019"),
        ("2020-01-01","2020-03-31","Q1 2020"),
        ("2020-07-01","2020-09-30","Q3 2020"),
        ("2021-01-01","2021-03-31","Q1 2021"),
        ("2021-07-01","2021-09-30","Q3 2021"),
        ("2022-01-01","2022-03-31","Q1 2022"),
        ("2022-07-01","2022-09-30","Q3 2022"),
        ("2023-01-01","2023-03-31","Q1 2023"),
        ("2023-07-01","2023-09-30","Q3 2023"),
        ("2024-01-01","2024-03-31","Q1 2024"),
        ("2024-07-01","2024-09-30","Q3 2024"),
    ]
    return [{"index":i,"label":l,"start":s,"end":e,"scene_date":None,
             "ndvi_mean":None,"status":"not_cached"}
            for i,(s,e,l) in enumerate(quarters)]


def get_temporal_frame(index: int) -> dict:
    """
    Return a single temporal frame with real PNG overlays from Colab data.
    """
    periods = get_temporal_periods()
    if not periods or index >= len(periods):
        return {"index": index, "status": "error", "error": "Index out of range"}

    period = periods[index]
    pngs   = render_frame_pngs(index)

    # NDVI mean for this time step
    ndvi_mean = None
    scores = _STORE.get("temporal_scores")
    if scores is not None and index < len(scores):
        ndvi_mean = float(scores[index])
    elif _STORE.get("ndvi_a") is not None:
        ndvi_a = _STORE["ndvi_a"]
        ndvi_b = _STORE.get("ndvi_b", ndvi_a)
        t = index / 11.0
        blended = ndvi_b * (1 - t) + ndvi_a * t
        ndvi_mean = float(np.nanmean(blended))

    return {
        "index":             index,
        "label":             period["label"],
        "scene_date":        period.get("scene_date"),
        "ndvi_mean":         ndvi_mean,
        "bsi_mean":          float(np.nanmean(_STORE["bsi_a"])) if _STORE.get("bsi_a") is not None else None,
        "mining_mean":       float(np.nanmean(_best_score())) if _best_score() is not None else None,
        "status":            "ok",
        "source":            "colab_ingest",
        **pngs,
    }


# ── Stats ──────────────────────────────────────────────────────────────────────

def get_detection_stats() -> dict:
    """Compute summary stats from Colab-ingested mining map."""
    score = _best_score()
    if score is None:
        return {}

    threshold = 0.35
    affected  = float((score > threshold).sum() * 0.36)
    critical  = float((score > 0.65).sum() * 0.36)
    peak      = float(score.max())

    return {
        "affected_area_ha":  _STORE.get("affected_area_ha") or round(affected, 1),
        "critical_area_ha":  _STORE.get("critical_area_ha") or round(critical, 1),
        "peak_score":        _STORE.get("peak_score") or round(peak, 3),
        "high_risk_pct":     round(critical / max(affected, 1) * 100, 1),
        "source":            "colab_spectral_rf",
        "ingested_at":       _STORE.get("ingested_at"),
    }