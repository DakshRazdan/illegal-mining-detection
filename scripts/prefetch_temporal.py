"""
scripts/prefetch_temporal.py — Caches all temporal NDVI composites.
OWNER: Gemini
"""
import sys
from pathlib import Path

# Add project root to PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingest.temporal_fetch import fetch_all_periods
from src.utils.logger import logger

def main():
    logger.info("Prefetching Temporal NDVI composites from Planetary Computer...")
    try:
        results = fetch_all_periods()
        ok_count = sum(1 for r in results if r['status'] == 'ok')
        logger.success(f"Prefetch complete. {ok_count} periods successfully cached to data/temporal/")
    except Exception as e:
        logger.error(f"Prefetch failed: {e}")

if __name__ == "__main__":
    main()
