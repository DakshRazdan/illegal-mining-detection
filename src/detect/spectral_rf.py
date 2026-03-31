"""
src/detect/spectral_rf.py — Spectral index-based mining detection.
OWNER: Antigravity Agent 2

Pipeline:
    1. compute_indices_extended()  — 6 spectral indices from Sentinel-2 bands
    2. compute_mining_score()      — weighted 6-index fusion (v2 weights)
    3. filter_false_positives()    — OSM Overpass mask for known non-mining land use
    4. classify_land_cover()       — unsupervised K-Means (4 classes)

Bands required (7-band stack):
    B03 (Green), B04 (Red), B05 (Red Edge 1), B07 (Red Edge 3),
    B08 (NIR), B11 (SWIR1), B12 (SWIR2)

All inputs: stackstac DataArray (stacked Sentinel-2 L2A).
All outputs: numpy arrays shaped (H, W), or DetectionResult list.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

import numpy as np
import requests
from sklearn.cluster import KMeans

from src.utils.logger import logger
from src.utils.config import SETTINGS
from src.types import DetectionResult, DetectionMethod

# ---------------------------------------------------------------------------
# Bands — updated to 7-band stack (v2)
# ---------------------------------------------------------------------------

SENTINEL2_BANDS = ["B04", "B08", "B11", "B03", "B05", "B07", "B12"]

# ---------------------------------------------------------------------------
# Normalisation helper (used inside score computation)
# ---------------------------------------------------------------------------

def norm(arr: np.ndarray) -> np.ndarray:
    """Clip negatives, normalise to [0, 1]. NaN-safe."""
    arr = np.nan_to_num(arr, nan=0.0)
    arr = np.clip(arr, 0, None)
    if arr.max() == 0:
        return arr
    return arr / arr.max()


# Keep public alias used by legacy callers / tests
def normalise(arr: np.ndarray) -> np.ndarray:
    return norm(arr)


# ---------------------------------------------------------------------------
# 1. Spectral indices — v2 (6-index, 7-band)
# ---------------------------------------------------------------------------

def compute_indices_extended(stack) -> tuple[
    np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray
]:
    """
    Compute 6 spectral indices from a 7-band Sentinel-2 stackstac DataArray.

    Returns
    -------
    ndvi  : Normalized Difference Vegetation Index
    bsi   : Bare Soil Index
    ndwi  : Normalized Difference Water Index
    nbr   : Normalized Burn Ratio
    cmi   : Clay Mineral Index   (SWIR1 / SWIR2)  ← new in v2
    reci  : Red Edge Chlorophyll Index             ← new in v2
    """
    red   = stack.sel(band="B04").values[0].astype(float)
    nir   = stack.sel(band="B08").values[0].astype(float)
    swir1 = stack.sel(band="B11").values[0].astype(float)
    green = stack.sel(band="B03").values[0].astype(float)
    re1   = stack.sel(band="B05").values[0].astype(float)
    re3   = stack.sel(band="B07").values[0].astype(float)
    swir2 = stack.sel(band="B12").values[0].astype(float)

    # Zero → NaN to avoid false spectral signals from no-data pixels
    for arr in [red, nir, swir1, green, re1, re3, swir2]:
        arr[arr == 0] = np.nan

    ndvi = (nir - red)    / (nir + red    + 1e-10)
    bsi  = ((swir1 + red) - (nir + green)) / ((swir1 + red) + (nir + green) + 1e-10)
    ndwi = (green - nir)  / (green + nir  + 1e-10)
    nbr  = (nir - swir1)  / (nir + swir1  + 1e-10)
    cmi  = (swir1 - swir2) / (swir1 + swir2 + 1e-10)   # Clay Mineral Index
    reci = (re3 / (re1 + 1e-10)) - 1                    # Red Edge Chlorophyll Index

    return ndvi, bsi, ndwi, nbr, cmi, reci


# ---------------------------------------------------------------------------
# 2. Mining score — v2 weights (6-index fusion)
# ---------------------------------------------------------------------------

def compute_mining_score(stack_before, stack_after) -> np.ndarray:
    """
    Compute per-pixel mining probability from bi-temporal 7-band stacks.

    Weights (v2, validated):
        ΔNDVI  0.25  — vegetation loss
        ΔBSI   0.20  — bare soil exposure
        ΔNDWI  0.15  — water disturbance
        ΔNBR   0.15  — burn/soil change
        ΔCMI   0.15  — clay mineral exposure (overburden dump signal)
        ΔRECI  0.10  — chlorophyll loss (canopy removal)

    Returns
    -------
    mining_score : np.ndarray shape (H, W), values in [0, 1]
    """
    ndvi_b, bsi_b, ndwi_b, nbr_b, cmi_b, reci_b = compute_indices_extended(stack_before)
    ndvi_a, bsi_a, ndwi_a, nbr_a, cmi_a, reci_a = compute_indices_extended(stack_after)

    delta_ndvi = norm(ndvi_b - ndvi_a)   # decrease in vegetation → +score
    delta_bsi  = norm(bsi_a  - bsi_b)    # increase in bare soil  → +score
    delta_ndwi = norm(ndwi_b - ndwi_a)   # decrease in water NDWI → +score
    delta_nbr  = norm(nbr_b  - nbr_a)    # decrease in NBR        → +score
    delta_cmi  = norm(cmi_a  - cmi_b)    # increase in clay minerals → +score
    delta_reci = norm(reci_b - reci_a)   # decrease in chlorophyll   → +score

    mining_score = (
        0.25 * delta_ndvi +
        0.20 * delta_bsi  +
        0.15 * delta_ndwi +
        0.15 * delta_nbr  +
        0.15 * delta_cmi  +
        0.10 * delta_reci
    )
    return norm(mining_score)


# ---------------------------------------------------------------------------
# 3. False positive filtering via OpenStreetMap
# ---------------------------------------------------------------------------

def filter_false_positives(
    mining_score: np.ndarray,
    aoi_bounds: tuple[float, float, float, float],
    timeout: int = 30,
) -> np.ndarray:
    """
    Zero out pixels over known residential, farmland, or industrial areas
    using OpenStreetMap Overpass API.

    Parameters
    ----------
    mining_score : (H, W) array
    aoi_bounds   : (min_lon, min_lat, max_lon, max_lat)
    timeout      : HTTP request timeout in seconds

    Returns
    -------
    filtered : (H, W) array with false-positive pixels zeroed
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    min_lon, min_lat, max_lon, max_lat = aoi_bounds

    query = f"""
    [out:json][timeout:25];
    (
      way["landuse"~"residential|farmland|farm|industrial"]
         ({min_lat},{min_lon},{max_lat},{max_lon});
      way["place"~"village|town|city|hamlet"]
         ({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out geom;
    """

    try:
        response = requests.get(overpass_url, params={"data": query}, timeout=timeout)
        response.raise_for_status()
        elements = response.json().get("elements", [])
        logger.info("OSM FP filter: {} excluded features for AOI bounds.", len(elements))
    except Exception as e:
        logger.warning("OSM Overpass request failed ({}). Skipping FP filter.", e)
        return mining_score

    h, w = mining_score.shape
    fp_mask = np.zeros((h, w), dtype=bool)

    for el in elements:
        if "geometry" not in el:
            continue
        for n in el["geometry"]:
            col = int((n["lon"] - min_lon) / (max_lon - min_lon) * w)
            row = int((max_lat - n["lat"]) / (max_lat - min_lat) * h)
            if 0 <= row < h and 0 <= col < w:
                fp_mask[row, col] = True

    filtered = mining_score.copy()
    filtered[fp_mask] = 0.0
    logger.debug("FP filter masked {}/{} pixels.", fp_mask.sum(), h * w)
    return filtered


# ---------------------------------------------------------------------------
# 4. K-Means land cover classification (4 classes)
# ---------------------------------------------------------------------------

def classify_land_cover(
    ndvi: np.ndarray,
    bsi: np.ndarray,
    ndwi: np.ndarray,
    nbr: np.ndarray,
    n_clusters: int = 4,
    random_state: int = 42,
) -> tuple[np.ndarray, dict[str, int]]:
    """
    Unsupervised K-Means classification on 4 spectral features.

    Classes assigned by highest centroid value per index:
        forest   → highest NDVI centroid
        mining   → highest BSI centroid
        water    → highest NDWI centroid
        degraded → residual class

    Returns
    -------
    labels  : (H, W) integer label array
    class_map : dict mapping class name → cluster index
    """
    h, w = ndvi.shape
    features = np.stack([
        np.nan_to_num(ndvi),
        np.nan_to_num(bsi),
        np.nan_to_num(ndwi),
        np.nan_to_num(nbr),
    ], axis=-1).reshape(-1, 4)

    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    kmeans.fit(features)
    labels = kmeans.predict(features).reshape(h, w)

    centers = kmeans.cluster_centers_
    forest_cls   = int(np.argmax(centers[:, 0]))   # highest NDVI
    mining_cls   = int(np.argmax(centers[:, 1]))   # highest BSI
    water_cls    = int(np.argmax(centers[:, 2]))   # highest NDWI
    degraded_cls = list({0, 1, 2, 3} - {forest_cls, mining_cls, water_cls})[0]

    class_map = {
        "forest":   forest_cls,
        "mining":   mining_cls,
        "water":    water_cls,
        "degraded": degraded_cls,
    }
    logger.info("K-Means classes: {}", class_map)
    return labels, class_map


# ---------------------------------------------------------------------------
# 5. Full detection runner — combines score + FP filter → DetectionResult list
# ---------------------------------------------------------------------------

def run_spectral_detection(
    stack_before,
    stack_after,
    aoi_bounds: tuple[float, float, float, float],
    threshold: Optional[float] = None,
    apply_fp_filter: bool = True,
) -> list[DetectionResult]:
    """
    End-to-end spectral detection:
      stack_before/after → mining_score → FP filter → threshold → DetectionResult list

    Parameters
    ----------
    stack_before   : stackstac DataArray (baseline period)
    stack_after    : stackstac DataArray (monitoring period)
    aoi_bounds     : (min_lon, min_lat, max_lon, max_lat)
    threshold      : mining_score threshold (default from settings.yaml)
    apply_fp_filter: whether to run OSM false-positive filter

    Returns
    -------
    list[DetectionResult]
    """
    cfg = SETTINGS.get("detection", {})
    if threshold is None:
        threshold = cfg.get("threshold", 0.5)
    pixel_area_ha = cfg.get("pixel_area_ha", 0.36)
    min_area_ha   = cfg.get("min_area_ha", 0.5)

    logger.info("Running spectral detection | threshold={} | FP filter={}", threshold, apply_fp_filter)

    # Score
    score = compute_mining_score(stack_before, stack_after)

    # FP filter
    if apply_fp_filter:
        score = filter_false_positives(score, aoi_bounds)

    # Threshold → binary mask
    mining_mask = score > threshold
    affected_ha = float(mining_mask.sum() * pixel_area_ha)
    logger.info("Mining mask: {} pixels flagged | {:.1f} ha total", mining_mask.sum(), affected_ha)

    # Convert mask to DetectionResult objects (one per connected region)
    from src.utils.geo_utils import mask_to_centroids
    min_lon, min_lat, max_lon, max_lat = aoi_bounds
    centroids = mask_to_centroids(mining_mask, min_lon, max_lon, min_lat, max_lat)

    from scipy import ndimage
    labeled, n_regions = ndimage.label(mining_mask)

    results: list[DetectionResult] = []
    for i, (lon, lat) in enumerate(centroids, start=1):
        region_pixels = int((labeled == i).sum())
        area_ha = region_pixels * pixel_area_ha

        if area_ha < min_area_ha:
            continue  # skip tiny detections (noise)

        region_scores = score[labeled == i]
        mean_score = float(np.nanmean(region_scores))

        det = DetectionResult(
            detection_id=f"SPEC-{uuid.uuid4().hex[:8].upper()}",
            lon=lon,
            lat=lat,
            area_ha=round(area_ha, 2),
            mining_score=round(mean_score, 4),
            method=DetectionMethod.SPECTRAL_RF,
            detected_at=datetime.utcnow(),
        )
        results.append(det)

    logger.success("Spectral detection complete: {} detections (>= {:.1f} ha).", len(results), min_area_ha)
    return results
