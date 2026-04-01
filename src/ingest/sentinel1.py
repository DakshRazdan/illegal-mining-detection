"""
src/ingest/sentinel1.py — Downloads Sentinel-1 SAR footprint metadata.


Uses asf-search to find radar footprints. Returns a stub GRD array for hackathon demo speed if time-limited.
"""

import asf_search as asf
from pathlib import Path
import numpy as np
from src.utils.logger import logger
from src.utils.config import SETTINGS

def ingest_sar_data() -> Path:
    logger.info("Starting Sentinel-1 SAR ingestion module (via ASF)")
    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "sar_composite.npy"

    aoi = SETTINGS.get("aoi", {})
    bbox = aoi.get("bbox", {"min_lon": 85.8, "min_lat": 23.5, "max_lon": 86.2, "max_lat": 23.8})
    # ASF search expects WKT bounds
    wkt = f"POLYGON(({bbox['min_lon']} {bbox['min_lat']}, {bbox['max_lon']} {bbox['min_lat']}, {bbox['max_lon']} {bbox['max_lat']}, {bbox['min_lon']} {bbox['max_lat']}, {bbox['min_lon']} {bbox['min_lat']}))"

    try:
        results = asf.geo_search(
            platform=[asf.PLATFORM.SENTINEL1],
            intersectsWith=wkt,
            maxResults=1,
            processingLevel=asf.PRODUCT_TYPE.GRD_HD,
            polarization=asf.POLARIZATION.VV_VH
        )
        if results:
            logger.success(f"Discovered SAR granule: {results[0].properties['sceneName']}")
        else:
            logger.warning("No SAR granules found in search window.")
    except Exception as e:
        logger.warning(f"ASF SAR Search failed (possibly no internet/auth): {e}")

    # For hackathon demo and keeping the pipeline agile, writing a stub composite array
    np.save(out_path, np.zeros((2, 256, 256))) # 2 bands (VV, VH)
    logger.info(f"Saved stub SAR composite to {out_path}.")
    
    return out_path

if __name__ == "__main__":
    ingest_sar_data()
