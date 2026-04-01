"""
src/ingest/temporal_fetch.py
Fetches Sentinel-2 L2A composites from Microsoft Planetary Computer.
Computes NDVI, BSI, NDWI, Turbidity, and Mining Score PNGs per frame.
Caches to data/temporal/ as .npz to avoid re-fetching.
"""

import traceback
import numpy as np
from pathlib import Path
import io
import base64
import warnings
warnings.filterwarnings('ignore')

import planetary_computer
import pystac_client
import stackstac
from PIL import Image

AOI = {
    "type": "Polygon",
    "coordinates": [[
        [85.8, 23.5], [86.2, 23.5],
        [86.2, 23.8], [85.8, 23.8],
        [85.8, 23.5]
    ]]
}

AOI_BOUNDS = [85.8, 23.5, 86.2, 23.8]  # [min_lon, min_lat, max_lon, max_lat]

DEFAULT_PERIODS = [
    ("2019-01-01", "2019-03-31", "Q1 2019"),
    ("2019-07-01", "2019-09-30", "Q3 2019"),
    ("2020-01-01", "2020-03-31", "Q1 2020"),
    ("2020-07-01", "2020-09-30", "Q3 2020"),
    ("2021-01-01", "2021-03-31", "Q1 2021"),
    ("2021-07-01", "2021-09-30", "Q3 2021"),
    ("2022-01-01", "2022-03-31", "Q1 2022"),
    ("2022-07-01", "2022-09-30", "Q3 2022"),
    ("2023-01-01", "2023-03-31", "Q1 2023"),
    ("2023-07-01", "2023-09-30", "Q3 2023"),
    ("2024-01-01", "2024-03-31", "Q1 2024"),
    ("2024-07-01", "2024-09-30", "Q3 2024"),
]

# Bands needed for all indices
BANDS = ["B03", "B04", "B05", "B07", "B08", "B11", "B12"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.abs(a + b) < 1e-6, 0.0, (a - b) / (a + b))


def _norm_to_uint8(arr: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
    clipped = np.clip(arr, vmin, vmax)
    scaled  = (clipped - vmin) / (vmax - vmin)
    return (scaled * 255).astype(np.uint8)


def _array_to_b64_png(arr: np.ndarray) -> str:
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _apply_colormap(arr_uint8: np.ndarray, cmap_name: str) -> np.ndarray:
    from matplotlib import cm
    cmap = cm.get_cmap(cmap_name)
    colored = cmap(arr_uint8 / 255.0)
    return (colored[:, :, :3] * 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Index computation
# ---------------------------------------------------------------------------

def compute_all_indices(stack) -> dict:
    """
    Compute NDVI, BSI, NDWI, Turbidity (NDTI), and Mining Score
    from a 7-band stackstac DataArray.
    Returns dict of {name: np.ndarray (H, W)}.
    """
    def band(name):
        arr = stack.sel(band=name).values[0].astype(float)
        arr[arr == 0] = np.nan
        return arr / 10000.0  # scale to reflectance

    red   = band("B04")
    nir   = band("B08")
    green = band("B03")
    swir1 = band("B11")
    swir2 = band("B12")
    re1   = band("B05")
    re3   = band("B07")

    ndvi = _safe_ratio(nir, red)
    bsi  = _safe_ratio((swir1 + red) - (nir + green),
                       (swir1 + red) + (nir + green))
    ndwi = _safe_ratio(green, nir)
    ndti = _safe_ratio(red, green)   # turbidity proxy

    # Clay mineral index + red edge chlorophyll
    cmi  = _safe_ratio(swir1, swir2)
    reci = np.where(re1 > 0, re3 / (re1 + 1e-10) - 1, 0.0)

    # Mining score — weighted fusion (same weights as spectral_rf.py)
    def norm01(a):
        a = np.nan_to_num(a, nan=0.0)
        a = np.clip(a, 0, None)
        return a / a.max() if a.max() > 0 else a

    # Use single-date heuristic (no baseline): high BSI + low NDVI = mining
    mining_score = (
        0.35 * norm01(-ndvi) +   # low vegetation
        0.30 * norm01(bsi)   +   # high bare soil
        0.20 * norm01(cmi)   +   # clay minerals (overburden)
        0.15 * norm01(reci * -1) # low chlorophyll
    )
    mining_score = np.clip(np.nan_to_num(mining_score, nan=0.0), 0, 1)

    return {
        "ndvi":     ndvi,
        "bsi":      bsi,
        "ndwi":     ndwi,
        "turbidity": ndti,
        "mining":   mining_score,
    }


def indices_to_pngs(indices: dict) -> dict:
    """Convert index arrays to base64 PNGs using appropriate colormaps."""
    configs = {
        "ndvi":      ("RdYlGn",  -0.2, 0.8),
        "bsi":       ("YlOrBr",  -0.3, 0.5),
        "ndwi":      ("Blues",   -0.5, 0.5),
        "turbidity": ("PuRd",    -0.2, 0.3),
        "mining":    ("hot_r",    0.0, 1.0),
    }
    pngs = {}
    for name, (cmap, vmin, vmax) in configs.items():
        if name not in indices:
            continue
        arr = np.nan_to_num(indices[name], nan=0.0)
        u8  = _norm_to_uint8(arr, vmin, vmax)
        rgb = _apply_colormap(u8, cmap)
        pngs[name] = _array_to_b64_png(rgb)
    return pngs


# ---------------------------------------------------------------------------
# Main fetch function
# ---------------------------------------------------------------------------

def fetch_ndvi_composite(start: str, end: str, label: str,
                         cache_dir: Path = Path("data/temporal")) -> dict:
    """
    Fetch best Sentinel-2 scene for a period, compute all indices,
    return base64 PNGs + stats. Results are cached as .npz.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{label.replace(' ', '_')}.npz"

    if cache_file.exists():
        data = np.load(cache_file, allow_pickle=True)
        return dict(data["result"].item())

    try:
        catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=planetary_computer.sign_inplace,
        )

        search = catalog.search(
            collections=["sentinel-2-l2a"],
            intersects=AOI,
            datetime=f"{start}/{end}",
            query={"eo:cloud_cover": {"lt": 25}},
        )
        items = list(search.items())

        if not items:
            result = {
                "label": label, "start": start, "end": end,
                "status": "no_data", "error": "No scenes found",
                "ndvi_png_b64": None, "rgb_png_b64": None,
                "bsi_png_b64": None, "ndwi_png_b64": None,
                "turbidity_png_b64": None, "mining_png_b64": None,
                "ndvi_mean": None, "bsi_mean": None,
                "mining_mean": None, "scene_date": None,
            }
            np.savez(cache_file, result=result)
            return result

        best_item  = min(items, key=lambda x: x.properties.get("eo:cloud_cover", 100))
        scene_date = best_item.datetime.strftime("%Y-%m-%d")
        cloud_cover = best_item.properties.get("eo:cloud_cover", 0)

        stack = stackstac.stack(
            [best_item],
            assets=BANDS,
            resolution=60,
            epsg=4326,
            chunksize=512,
        ).compute()

        indices = compute_all_indices(stack)
        pngs    = indices_to_pngs(indices)

        # True-colour RGB
        def raw_band(name):
            arr = stack.sel(band=name).values[0].astype(float)
            arr[arr == 0] = np.nan
            return arr

        r = np.nan_to_num(raw_band("B04"))
        g = np.nan_to_num(raw_band("B03"))
        b = np.nan_to_num(raw_band("B02")) if "B02" in stack.band.values else r * 0.8
        mx = max(r.max(), g.max(), b.max())
        if mx > 0:
            r, g, b = r/mx*255, g/mx*255, b/mx*255
        rgb_arr = np.stack([r.clip(0,255).astype(np.uint8),
                            g.clip(0,255).astype(np.uint8),
                            b.clip(0,255).astype(np.uint8)], axis=-1)
        rgb_b64 = _array_to_b64_png(rgb_arr)

        result = {
            "label":            label,
            "start":            start,
            "end":              end,
            "ndvi_png_b64":     pngs.get("ndvi"),
            "bsi_png_b64":      pngs.get("bsi"),
            "ndwi_png_b64":     pngs.get("ndwi"),
            "turbidity_png_b64":pngs.get("turbidity"),
            "mining_png_b64":   pngs.get("mining"),
            "rgb_png_b64":      rgb_b64,
            "ndvi_mean":        float(np.nanmean(indices["ndvi"])),
            "bsi_mean":         float(np.nanmean(indices["bsi"])),
            "mining_mean":      float(np.nanmean(indices["mining"])),
            "cloud_cover":      float(cloud_cover),
            "scene_date":       scene_date,
            "status":           "ok",
            "error":            None,
        }

        np.savez(cache_file, result=result)
        return result

    except Exception as e:
        traceback.print_exc()
        result = {
            "label": label, "start": start, "end": end,
            "status": "error", "error": str(e),
            "ndvi_png_b64": None, "rgb_png_b64": None,
            "bsi_png_b64": None, "ndwi_png_b64": None,
            "turbidity_png_b64": None, "mining_png_b64": None,
            "ndvi_mean": None, "bsi_mean": None,
            "mining_mean": None, "scene_date": None,
        }
        return result


def fetch_all_periods(periods=DEFAULT_PERIODS) -> list[dict]:
    results = []
    for start, end, label in periods:
        print(f"Fetching {label}...")
        r = fetch_ndvi_composite(start, end, label)
        results.append(r)
        print(f"  {r['status']} — {r.get('scene_date','N/A')}")
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\nFetched {ok}/{len(periods)} periods successfully.")
    return results