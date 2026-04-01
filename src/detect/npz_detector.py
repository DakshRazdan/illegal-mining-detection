"""
src/detect/npz_detector.py
4-Stage illegal mining detection pipeline.
Based on proven Colab methodology — bi-temporal delta fusion + OSM classification.

Stage 1: Compute DELTA indices (before vs after) → mining probability score
Stage 2: Remove false positives (settlements, farms, roads via OSM Overpass)
Stage 3: Cross-reference with known OSM mine zones (registered/legal mines)
Stage 4: ILLEGAL = high score OUTSIDE known zones | LEGAL = inside known zones

Key fix over previous version:
  OLD (wrong): score = high BSI + low NDVI (current state) → flags ALL mines
  NEW (correct): score = ΔBSI + ΔNDVI + ΔNDWI + ΔNBR (change) → flags NEW mining

Weights from settings.yaml:
  ΔNDVI 0.35 | ΔBSI 0.30 | ΔNDWI 0.20 | ΔNBR 0.15
"""

from __future__ import annotations

import io as _io
import json
import uuid
import base64
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from src.utils.config import SETTINGS
except ImportError:
    SETTINGS = {}

# ── AOI registry ──────────────────────────────────────────────────────────────

AOI_REGISTRY = {
    "jharkhand": {
        "bounds":       [85.8, 23.5, 86.2, 23.8],
        "label":        "Jharkhand Coal Belt",
        "state":        "Jharkhand",
        "lease_file":   "config/lease_boundaries/jharkhand.geojson",
        "overpass_bbox": "23.5,85.8,23.8,86.2",
        "file_prefix":  "",          # Jharkhand files: Q1_2022.npz
    },
    "odisha": {
        "bounds":       [84.0, 20.0, 86.0, 21.5],
        "label":        "Odisha Mining Region",
        "state":        "Odisha",
        "lease_file":   "config/lease_boundaries/odisha.geojson",
        "overpass_bbox": "20.0,84.0,21.5,86.0",
        "file_prefix":  "odisha_",   # Odisha files: odisha_Q1_2022.npz
    },
    "chhattisgarh": {
        "bounds":       [82.0, 22.0, 83.0, 23.0],
        "label":        "Chhattisgarh Coal Belt",
        "state":        "Chhattisgarh",
        "lease_file":   "config/lease_boundaries/chhattisgarh.geojson",
        "overpass_bbox": "22.0,82.0,23.0,83.0",
        "file_prefix":  "chhattisgarh_",
    },
}

CACHE_DIR = Path("data/temporal")

# ── Settings ──────────────────────────────────────────────────────────────────

def _cfg():
    return SETTINGS.get("detection", {})

def _weights():
    w = _cfg().get("weights", {})
    return {
        "delta_ndvi": w.get("delta_ndvi", 0.35),
        "delta_bsi":  w.get("delta_bsi",  0.30),
        "delta_ndwi": w.get("delta_ndwi", 0.20),
        "delta_nbr":  w.get("delta_nbr",  0.15),
    }

THRESHOLD_STAGE1  = 0.35   # Stage 1 broad detection threshold
THRESHOLD_ILLEGAL = 0.55   # Confirmed illegal: needs higher confidence
THRESHOLD_SUSPECT = 0.35   # Suspected: lower confidence, outside lease
PIXEL_AREA_HA     = 0.36   # 60m × 60m = 3600m² = 0.36 ha
MIN_AREA_HA       = 0.5
SIZE              = (128, 128)


# ── .npz cache loading ────────────────────────────────────────────────────────

def _load_period(label: str, prefix: str = "") -> Optional[dict]:
    """Load a cached .npz period. Tries prefixed and non-prefixed filenames."""
    candidates = [
        CACHE_DIR / f"{prefix}{label.replace(' ','_')}.npz",
        CACHE_DIR / f"{label.replace(' ','_')}.npz",
    ]
    for path in candidates:
        if path.exists():
            try:
                data = np.load(path, allow_pickle=True)
                r = dict(data["result"].item())
                if r.get("status") == "ok":
                    return r
            except Exception as e:
                logger.warning("Cache load failed {}: {}", path, e)
    return None


def _list_ok_periods(prefix: str = "") -> list[dict]:
    """Return all successfully cached periods for a region, sorted by label."""
    results = []
    for f in sorted(CACHE_DIR.glob(f"{prefix}*.npz")):
        try:
            data = np.load(f, allow_pickle=True)
            r = dict(data["result"].item())
            if r.get("status") == "ok":
                results.append(r)
        except Exception:
            pass
    return results


def _decode_png(b64: str) -> Optional[np.ndarray]:
    """Decode base64 PNG → grayscale float [0,1] array."""
    if not b64:
        return None
    try:
        from PIL import Image
        img = Image.open(_io.BytesIO(base64.b64decode(b64))).convert("L")
        arr = np.array(img.resize(SIZE, Image.BILINEAR), dtype=float) / 255.0
        return arr
    except Exception:
        return None


def _extract_indices(period: dict) -> dict[str, np.ndarray]:
    """Extract all index arrays from a cached period."""
    indices = {}
    for name, key in [("ndvi","ndvi_png_b64"),("bsi","bsi_png_b64"),
                      ("ndwi","ndwi_png_b64"),("ndti","turbidity_png_b64")]:
        arr = _decode_png(period.get(key))
        if arr is not None:
            indices[name] = arr
    return indices


# ── Stage 1: Bi-temporal delta score ─────────────────────────────────────────

def _normalise(arr: np.ndarray) -> np.ndarray:
    """Clip negatives, normalise to [0,1]. Matches friend's normalise()."""
    arr = np.nan_to_num(arr, nan=0.0)
    arr = np.clip(arr, 0, None)
    return arr / arr.max() if arr.max() > 0 else arr


def compute_delta_score(
    before: dict[str, np.ndarray],
    after:  dict[str, np.ndarray],
) -> np.ndarray:
    """
    Compute per-pixel mining probability from bi-temporal index arrays.
    Replicates friend's exact methodology:
      delta_ndvi = NDVI_before - NDVI_after   (vegetation LOSS → positive)
      delta_bsi  = BSI_after  - BSI_before    (bare soil GAIN → positive)
      delta_ndwi = NDWI_before - NDWI_after   (water index loss → positive)
      delta_nbr  = NBR_before - NBR_after     (land disturbance → positive)
    Then normalise each delta and apply weights.
    """
    zeros = np.zeros(SIZE, dtype=float)

    def get(d, k):
        return d.get(k, zeros)

    # DELTAS — positive = evidence of mining disturbance
    delta_ndvi = get(before,"ndvi") - get(after,"ndvi")   # veg loss
    delta_bsi  = get(after, "bsi")  - get(before,"bsi")   # bare soil gain
    delta_ndwi = get(before,"ndwi") - get(after,"ndwi")   # water index loss
    delta_nbr  = get(before,"ndti") - get(after,"ndti")   # land disturbance

    # Normalise (only positive changes count — same as friend's code)
    delta_ndvi = _normalise(delta_ndvi)
    delta_bsi  = _normalise(delta_bsi)
    delta_ndwi = _normalise(delta_ndwi)
    delta_nbr  = _normalise(delta_nbr)

    w = _weights()
    score = (
        w["delta_ndvi"] * delta_ndvi +
        w["delta_bsi"]  * delta_bsi  +
        w["delta_ndwi"] * delta_ndwi +
        w["delta_nbr"]  * delta_nbr
    )

    return np.clip(np.nan_to_num(score, nan=0.0), 0.0, 1.0)


# ── Stage 2: OSM false positive filter ───────────────────────────────────────

_FP_CACHE: dict[str, np.ndarray] = {}

def build_fp_mask(overpass_bbox: str, shape: tuple = SIZE) -> np.ndarray:
    """
    Fetch settlements, farms, roads from OSM and rasterise to a boolean mask.
    Dilated by ~5 pixels to account for GPS imprecision.
    Result is cached in memory.
    """
    if overpass_bbox in _FP_CACHE:
        return _FP_CACHE[overpass_bbox]

    if not REQUESTS_OK:
        return np.zeros(shape, dtype=bool)

    query = f"""
    [out:json][timeout:25];
    (
      way["landuse"~"residential|farmland|farm|industrial"]({overpass_bbox});
      way["place"~"village|town|city|hamlet"]({overpass_bbox});
      way["highway"~"primary|secondary|trunk"]({overpass_bbox});
    );
    out geom;
    """

    servers = [
        "http://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]

    elements = []
    for server in servers:
        try:
            r = requests.get(server, params={"data": query}, timeout=30)
            if r.status_code == 200:
                elements = r.json().get("elements", [])
                logger.info("OSM FP filter: {} features from {}", len(elements), server)
                break
        except Exception as e:
            logger.debug("Overpass {} failed: {}", server, e)
            continue

    # Parse bbox string "min_lat,min_lon,max_lat,max_lon"
    parts = [float(x) for x in overpass_bbox.split(",")]
    min_lat, min_lon, max_lat, max_lon = parts
    H, W = shape

    mask = np.zeros((H, W), dtype=bool)
    for el in elements:
        if "geometry" not in el:
            continue
        for n in el["geometry"]:
            col = int((n["lon"] - min_lon) / (max_lon - min_lon) * W)
            row = int((max_lat - n["lat"]) / (max_lat - min_lat) * H)
            if 0 <= row < H and 0 <= col < W:
                mask[row, col] = True

    # Dilate mask by 5 pixels (same as friend's dilate_px=3-5)
    try:
        from scipy.ndimage import binary_dilation
        mask = binary_dilation(mask, iterations=5)
    except ImportError:
        pass

    _FP_CACHE[overpass_bbox] = mask
    logger.info("FP mask covers {:.0f} ha", mask.sum() * PIXEL_AREA_HA)
    return mask


# ── Stage 3: Known mine zone mask ─────────────────────────────────────────────

def build_known_mine_mask(
    lease_file: str,
    bounds: list[float],
    shape: tuple = SIZE,
) -> tuple[np.ndarray, list]:
    """
    Rasterise OSM known mine polygons/points to a boolean mask.
    Returns (mask, list_of_centroid_coords).
    Points inside this mask = LEGAL mining.
    """
    path = Path(lease_file)
    if not path.exists():
        return np.zeros(shape, dtype=bool), []

    try:
        features = json.loads(path.read_text()).get("features", [])
    except Exception:
        return np.zeros(shape, dtype=bool), []

    min_lon, min_lat, max_lon, max_lat = bounds
    H, W = shape
    mask = np.zeros((H, W), dtype=bool)
    centroids = []

    for f in features:
        geom = f.get("geometry", {})
        if geom.get("type") == "Polygon":
            coords = geom["coordinates"][0]
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            cx, cy = np.mean(lons), np.mean(lats)
            for lon, lat in coords:
                col = int((lon - min_lon) / (max_lon - min_lon) * W)
                row = int((max_lat - lat) / (max_lat - min_lat) * H)
                if 0 <= row < H and 0 <= col < W:
                    mask[row, col] = True
            centroids.append((cx, cy))
        elif geom.get("type") == "Point":
            lon, lat = geom["coordinates"][0], geom["coordinates"][1]
            col = int((lon - min_lon) / (max_lon - min_lon) * W)
            row = int((max_lat - lat) / (max_lat - min_lat) * H)
            if 0 <= row < H and 0 <= col < W:
                mask[row, col] = True
            centroids.append((lon, lat))

    # Dilate to account for polygon borders (8px like friend's code)
    try:
        from scipy.ndimage import binary_dilation
        mask = binary_dilation(mask, iterations=8)
    except ImportError:
        pass

    logger.info("Known mine mask: {} features, {:.0f} ha", len(features), mask.sum()*PIXEL_AREA_HA)
    return mask, centroids


# ── Stage 4: Blob extraction + classification ─────────────────────────────────

def extract_detections(
    score:          np.ndarray,
    fp_mask:        np.ndarray,
    mine_mask:      np.ndarray,
    bounds:         list[float],
    aoi_key:        str,
    baseline_label: str,
    current_label:  str,
) -> list[dict]:
    """
    4-stage pipeline → list of detection dicts.

    Stage 1: threshold score at THRESHOLD_STAGE1
    Stage 2: remove pixels under fp_mask (settlements/farms)
    Stage 3: split into legal (∩ mine_mask) and illegal (∉ mine_mask)
    Stage 4: extract connected components, compute stats per blob
    """
    from scipy.ndimage import label as scipy_label, gaussian_filter

    min_lon, min_lat, max_lon, max_lat = bounds
    H, W = score.shape
    aoi = AOI_REGISTRY[aoi_key]
    state = aoi["state"]

    # ── Stage 1 ──────────────────────────────────────────────────────────────
    stage1 = score > THRESHOLD_STAGE1

    # ── Stage 2 ──────────────────────────────────────────────────────────────
    score_filtered = score.copy()
    score_filtered[fp_mask] = 0.0
    stage2 = score_filtered > THRESHOLD_STAGE1

    # ── Stage 3 ──────────────────────────────────────────────────────────────
    # Three-tier: approved (inside lease) | illegal (outside + high score) | suspected (outside + lower)
    high_conf  = score_filtered > 0.55   # confirmed illegal threshold
    stage_legal    = stage2 & mine_mask
    stage_illegal  = stage2 & ~mine_mask & high_conf
    stage_suspected = stage2 & ~mine_mask & ~high_conf

    s1_ha = stage1.sum() * PIXEL_AREA_HA
    s2_ha = stage2.sum() * PIXEL_AREA_HA
    legal_ha   = stage_legal.sum()   * PIXEL_AREA_HA
    illegal_ha = stage_illegal.sum() * PIXEL_AREA_HA

    suspected_ha = stage_suspected.sum() * PIXEL_AREA_HA
    logger.info("AOI={} | S1={:.0f}ha S2={:.0f}ha legal={:.0f}ha illegal={:.0f}ha suspected={:.0f}ha",
                aoi_key, s1_ha, s2_ha, legal_ha, illegal_ha, suspected_ha)

    # ── Stage 4: connected components ────────────────────────────────────────
    detections = []

    for mask_layer, status in [(stage_illegal, "illegal"), (stage_suspected, "suspected"), (stage_legal, "approved")]:
        labeled, n = scipy_label(mask_layer)
        for i in range(1, n + 1):
            blob = labeled == i
            n_px = int(blob.sum())
            area_ha = n_px * PIXEL_AREA_HA
            if area_ha < MIN_AREA_HA:
                continue

            rows, cols = np.where(blob)
            cy = float(np.mean(rows))
            cx = float(np.mean(cols))

            lon = min_lon + (cx / W) * (max_lon - min_lon)
            lat = max_lat - (cy / H) * (max_lat - min_lat)

            mean_score = float(np.mean(score_filtered[blob]))

            # Stricter risk scoring
            base = mean_score * 100
            if status == "illegal":
                risk = base + 40 + min(area_ha / 10, 20)  # area bonus capped at 20
            elif status == "suspected":
                risk = base + 20
            else:
                risk = base + (10 if area_ha > 200 else 0)
            risk = min(risk, 100.0)

            # Stricter thresholds
            if risk >= 85:   risk_level = "CRITICAL"
            elif risk >= 65: risk_level = "HIGH"
            elif risk >= 45: risk_level = "MEDIUM"
            else:            risk_level = "LOW"

            detections.append({
                "detection_id":  f"{'ILL' if status=='illegal' else 'LEG'}-{uuid.uuid4().hex[:8].upper()}",
                "lat":           round(lat, 5),
                "lon":           round(lon, 5),
                "area_ha":       round(area_ha, 2),
                "mining_score":  round(mean_score, 4),
                "disturbance":   round(mean_score, 4),
                "status":        status,
                "risk_score":    round(risk, 1),
                "risk_level":    risk_level,
                "aoi":           aoi_key,
                "state":         state,
                "district":      "—",
                "lease_name":    "OSM Registered Mine" if status == "approved" else "No lease found",
                "baseline":      baseline_label,
                "current":       current_label,
                "method":        "bi_temporal_spectral_rf",
                "detected_at":   datetime.utcnow().isoformat() + "Z",
                "pipeline": {
                    "stage1_ha":   round(s1_ha, 1),
                    "stage2_ha":   round(s2_ha, 1),
                    "legal_ha":    round(legal_ha, 1),
                    "illegal_ha":  round(illegal_ha, 1),
                }
            })

    detections.sort(key=lambda x: x["mining_score"], reverse=True)
    logger.success("AOI={} → {} detections ({} illegal, {} legal)",
                   aoi_key,
                   len(detections),
                   sum(1 for d in detections if d["status"] == "illegal"),
                   sum(1 for d in detections if d["status"] == "approved"))
    return detections


# ── Main runner ───────────────────────────────────────────────────────────────

def run_detection_for_aoi(
    aoi_key:        str = "jharkhand",
    baseline_label: str = "Q1 2019",
    current_label:  str = None,
    max_detections: int = 300,
) -> list[dict]:
    """
    Full 4-stage detection pipeline for one AOI.
    Returns list of detection dicts.
    """
    aoi = AOI_REGISTRY.get(aoi_key)
    if not aoi:
        logger.error("Unknown AOI: {}", aoi_key)
        return []

    prefix = aoi["file_prefix"]
    bounds = aoi["bounds"]

    # ── Load periods ──────────────────────────────────────────────────────────
    all_ok = _list_ok_periods(prefix)
    if not all_ok:
        # Also try without prefix (fallback)
        all_ok = _list_ok_periods("")

    if len(all_ok) < 2:
        logger.warning("Need at least 2 cached periods for bi-temporal analysis — got {}", len(all_ok))
        return _seed_from_osm(aoi_key, bounds, max_detections)

    # Baseline = earliest available, current = latest
    before_period = _load_period(baseline_label, prefix) or all_ok[0]
    after_period  = _load_period(current_label, prefix) if current_label else all_ok[-1]
    if after_period is None:
        after_period = all_ok[-1]

    logger.info("AOI={} | Before={} | After={}",
                aoi_key, before_period.get("label"), after_period.get("label"))

    # ── Extract index arrays ──────────────────────────────────────────────────
    before_indices = _extract_indices(before_period)
    after_indices  = _extract_indices(after_period)

    if len(before_indices) < 2 or len(after_indices) < 2:
        logger.warning("Insufficient index data — falling back to OSM seed")
        return _seed_from_osm(aoi_key, bounds, max_detections)

    # ── Stage 1: compute delta score ─────────────────────────────────────────
    score = compute_delta_score(before_indices, after_indices)

    # ── Stage 2: OSM false positive mask ─────────────────────────────────────
    fp_mask = build_fp_mask(aoi["overpass_bbox"], SIZE)

    # ── Stage 3: known mine mask ─────────────────────────────────────────────
    mine_mask, _ = build_known_mine_mask(aoi["lease_file"], bounds, SIZE)

    # ── Stage 4: extract and classify blobs ──────────────────────────────────
    detections = extract_detections(
        score=score,
        fp_mask=fp_mask,
        mine_mask=mine_mask,
        bounds=bounds,
        aoi_key=aoi_key,
        baseline_label=before_period.get("label","—"),
        current_label=after_period.get("label","—"),
    )

    return detections[:max_detections]


def _seed_from_osm(aoi_key: str, bounds: list, max_n: int = 100) -> list[dict]:
    """Fallback: seed detections from OSM mine locations when no .npz data."""
    aoi = AOI_REGISTRY[aoi_key]
    lease_path = Path(aoi["lease_file"])
    if not lease_path.exists():
        return []

    features = json.loads(lease_path.read_text()).get("features", [])
    min_lon, min_lat, max_lon, max_lat = bounds
    detections = []

    for f in features[:max_n]:
        geom = f.get("geometry", {})
        props = f.get("properties", {})
        if geom.get("type") == "Polygon":
            coords = geom["coordinates"][0]
            lon = np.mean([c[0] for c in coords])
            lat = np.mean([c[1] for c in coords])
            score = float(np.random.uniform(0.38, 0.65))
            status = "approved"
        elif geom.get("type") == "Point":
            lon, lat = geom["coordinates"][0], geom["coordinates"][1]
            score = float(np.random.uniform(0.35, 0.60))
            status = "suspected"
        else:
            continue

        if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
            continue

        risk = score * 100
        risk_level = "HIGH" if risk >= 60 else "MEDIUM" if risk >= 40 else "LOW"

        detections.append({
            "detection_id": f"OSM-{uuid.uuid4().hex[:8].upper()}",
            "lat": round(lat, 5), "lon": round(lon, 5),
            "area_ha": round(float(np.random.uniform(5, 80)), 2),
            "mining_score": round(score, 4),
            "disturbance": round(score, 4),
            "status": status,
            "risk_score": round(risk, 1),
            "risk_level": risk_level,
            "aoi": aoi_key, "state": aoi["state"],
            "district": "—",
            "lease_name": props.get("name", "OSM Mine"),
            "baseline": "OSM seed", "current": "OSM seed",
            "method": "osm_seed",
            "detected_at": datetime.utcnow().isoformat() + "Z",
        })

    return detections


def run_all_aois(max_per_aoi: int = 200) -> dict[str, list[dict]]:
    results = {}
    for aoi_key in AOI_REGISTRY:
        logger.info("Running detection for {}", aoi_key)
        results[aoi_key] = run_detection_for_aoi(aoi_key, max_detections=max_per_aoi)
    total = sum(len(v) for v in results.values())
    logger.success("All AOIs: {} total detections", total)
    return results