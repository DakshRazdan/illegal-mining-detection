"""
Fetches Sentinel-2 NDVI composites for a time series from 
Microsoft Planetary Computer. Returns PNG tiles suitable for 
map overlay rendering.
"""

import planetary_computer
import pystac_client
import stackstac
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import io
import base64
from PIL import Image
import warnings
warnings.filterwarnings('ignore')

AOI = {
    "type": "Polygon",
    "coordinates": [[
        [85.8, 23.5], [86.2, 23.5],
        [86.2, 23.8], [85.8, 23.8],
        [85.8, 23.5]
    ]]
}

AOI_BOUNDS = [85.8, 23.5, 86.2, 23.8]  # [min_lon, min_lat, max_lon, max_lat]

# Time periods to fetch — quarterly from 2019 to 2024
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

def fetch_ndvi_composite(start: str, end: str, label: str, 
                          cache_dir: Path = Path("data/temporal")) -> dict:
    """
    Fetch best Sentinel-2 image for a time period, compute NDVI,
    return as base64 PNG + stats.
    
    Returns:
    {
        "label": str,
        "start": str,
        "end": str,
        "ndvi_png_b64": str,    # base64 encoded PNG for map overlay
        "rgb_png_b64": str,     # base64 encoded true-color PNG
        "ndvi_mean": float,
        "ndvi_min": float,
        "ndvi_max": float,
        "cloud_cover": float,
        "scene_date": str,
        "status": "ok" | "no_data" | "error",
        "error": str or None
    }
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{label.replace(' ', '_')}.npz"
    
    # Return cached if exists
    if cache_file.exists():
        data = np.load(cache_file, allow_pickle=True)
        return dict(data['result'].item())
    
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
                "ndvi_mean": None, "scene_date": None
            }
            np.savez(cache_file, result=result)
            return result
        
        # Pick lowest cloud cover scene
        best_item = min(items, key=lambda x: x.properties.get("eo:cloud_cover", 100))
        scene_date = best_item.datetime.strftime("%Y-%m-%d")
        cloud_cover = best_item.properties.get("eo:cloud_cover", 0)
        
        # Fetch bands
        stack = stackstac.stack(
            [best_item],
            assets=["B04", "B08", "B03"],
            resolution=60,
            epsg=4326,
            chunksize=512
        ).compute()
        
        red   = stack.sel(band="B04").values[0].astype(float)
        nir   = stack.sel(band="B08").values[0].astype(float)
        green = stack.sel(band="B03").values[0].astype(float)
        
        red[red == 0] = np.nan
        nir[nir == 0] = np.nan
        green[green == 0] = np.nan
        
        # Compute NDVI
        ndvi = (nir - red) / (nir + red + 1e-10)
        ndvi = np.nan_to_num(ndvi, nan=0.0)
        ndvi = np.clip(ndvi, -1, 1)
        
        # NDVI → colored PNG (RdYlGn colormap: red=bare, green=vegetation)
        ndvi_norm = ((ndvi + 1) / 2 * 255).astype(np.uint8)
        ndvi_colored = apply_rdylgn_colormap(ndvi_norm)
        ndvi_png_b64 = array_to_b64_png(ndvi_colored)
        
        # True color RGB PNG
        r = np.nan_to_num(red,   nan=0)
        g = np.nan_to_num(green, nan=0)
        b = np.nan_to_num(red,   nan=0)  # approximate blue with red
        rgb = np.stack([
            np.clip(r / r.max() * 255, 0, 255).astype(np.uint8),
            np.clip(g / g.max() * 255, 0, 255).astype(np.uint8),
            np.clip(b / b.max() * 255, 0, 255).astype(np.uint8),
        ], axis=-1)
        rgb_png_b64 = array_to_b64_png(rgb)
        
        result = {
            "label": label,
            "start": start,
            "end": end,
            "ndvi_png_b64": ndvi_png_b64,
            "rgb_png_b64": rgb_png_b64,
            "ndvi_mean": float(np.nanmean(ndvi)),
            "ndvi_min": float(np.nanmin(ndvi)),
            "ndvi_max": float(np.nanmax(ndvi)),
            "cloud_cover": float(cloud_cover),
            "scene_date": scene_date,
            "status": "ok",
            "error": None
        }
        
        np.savez(cache_file, result=result)
        return result
    
    except Exception as e:
        result = {
            "label": label, "start": start, "end": end,
            "status": "error", "error": str(e),
            "ndvi_png_b64": None, "rgb_png_b64": None,
            "ndvi_mean": None, "scene_date": None
        }
        return result


def apply_rdylgn_colormap(arr_uint8: np.ndarray) -> np.ndarray:
    """Apply Red-Yellow-Green colormap to grayscale array."""
    from matplotlib import cm
    colored = cm.RdYlGn(arr_uint8 / 255.0)
    return (colored[:, :, :3] * 255).astype(np.uint8)


def array_to_b64_png(arr: np.ndarray) -> str:
    """Convert numpy array to base64 PNG string."""
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def fetch_all_periods(periods=DEFAULT_PERIODS) -> list[dict]:
    """
    Fetch NDVI composites for all time periods.
    Skips periods with no data gracefully.
    Returns list of result dicts, status ok or no_data.
    """
    results = []
    for start, end, label in periods:
        print(f"Fetching {label}...")
        result = fetch_ndvi_composite(start, end, label)
        results.append(result)
        print(f"  {result['status']} — {result.get('scene_date', 'N/A')}")
    
    ok_count = sum(1 for r in results if r['status'] == 'ok')
    print(f"\nFetched {ok_count}/{len(periods)} periods successfully.")
    return results
