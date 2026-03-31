"""
src/ingest/sentinel2.py — Downloads Sentinel-2 L2A optical data.
OWNER: Gemini (Takes over Claude Code Terminal 1)

Retrieves 7 bands for bi-temporal analysis via Microsoft Planetary Computer STAC.
Saves before/after stacks to data/processed/.
"""

import os
from pathlib import Path
import numpy as np
import pystac_client
import planetary_computer
import stackstac
from src.utils.logger import logger
from src.utils.config import SETTINGS

BANDS = ["B04", "B08", "B11", "B03", "B05", "B07", "B12"]
# Needs SCL for cloud masking later
ASSETS = BANDS + ["SCL"]

def ingest_optical_data() -> tuple[Path, Path]:
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    before_path = out_dir / "stack_before.npy"
    after_path = out_dir / "stack_after.npy"

    aoi = SETTINGS.get("aoi", {})
    bbox = aoi.get("bbox", {"min_lon": 85.8, "min_lat": 23.5, "max_lon": 86.2, "max_lat": 23.8})
    bbox_list = [bbox["min_lon"], bbox["min_lat"], bbox["max_lon"], bbox["max_lat"]]

    sat = SETTINGS.get("satellite", {}).get("sentinel2", {})
    before_period = sat.get("before_period", "2019-01-01/2019-12-31")
    after_period = sat.get("after_period", "2023-01-01/2023-12-31")

    logger.info("Initializing PySTAC client for Planetary Computer...")
    try:
        catalog = pystac_client.Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=planetary_computer.sign_inplace,
        )
    except Exception as e:
        logger.error(f"Failed to connect to Planetary Computer STAC: {e}")
        return before_path, after_path

    # Function to fetch and process a stack
    def process_period(period_string: str, out_file: Path) -> None:
        logger.info(f"Querying S2 for {period_string} with bbox {bbox_list}...")
        search = catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox_list,
            datetime=period_string,
            query={"eo:cloud_cover": {"lt": 20}}
        )
        items = list(search.items())
        if not items:
            logger.warning(f"No items found for {period_string}.")
            # Write a stub zeros array to prevent pipeline crash if API rate limits
            np.save(out_file, np.zeros((7, 256, 256)))
            return

        logger.info(f"Found {len(items)} items. Stacking scenes...")
        
        # We take just a few to save memory, taking least cloudy
        items = sorted(items, key=lambda x: x.properties.get("eo:cloud_cover", 100))[:5]

        # Use stackstac to mosaic. 
        # Resolution 60m to save processing time during hackathon, EPSG 32645 
        try:
            stack = stackstac.stack(
                items,
                assets=ASSETS,
                bounds_latlon=bbox_list,
                epsg=32645,
                resolution=60,
                chunksize=512,
            )
            # Compute temporal median to remove transient clouds
            median = stack.median(dim="time", skipna=True).compute()
            
            # Save the result as a numpy array, shape: (Bands, H, W)
            arr = median.values
            np.save(out_file, arr)
            logger.success(f"Saved {out_file} with shape {arr.shape}")
        except Exception as e:
            logger.error(f"Failed to process stack: {e}")
            np.save(out_file, np.zeros((len(ASSETS), 256, 256)))

    process_period(before_period, before_path)
    process_period(after_period, after_path)

    return before_path, after_path

if __name__ == "__main__":
    ingest_optical_data()
