"""
scripts/seed_db.py — Seed PostGIS database with lease boundaries and sample data.
OWNER: Antigravity Agent 1

Usage:
    python scripts/seed_db.py [--geojson-only]

    --geojson-only : Skip PostGIS, only validate GeoJSON files (useful without Docker)
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from src.utils.logger import logger
from src.utils.config import SETTINGS


# ---------------------------------------------------------------------------
# GeoJSON seeding (always runs — no DB required)
# ---------------------------------------------------------------------------

def seed_geojson() -> None:
    """Validate and report on GeoJSON config files."""
    root = Path(__file__).resolve().parents[1]
    files = {
        "AOI": root / "config" / "aoi.geojson",
        "Lease Boundaries": root / "config" / "lease_boundaries" / "jharkhand_sample.geojson",
        "EC Records": root / "config" / "ec_records.json",
        "Land Records": root / "config" / "land_records.json",
    }

    logger.info("Validating GeoJSON / config files...")
    for name, path in files.items():
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            count = len(data.get("features", data.get("ec_records", data.get("land_records", []))))
            logger.success("  ✓ {} — {} records ({})", name, count, path.name)
        else:
            logger.error("  ✗ {} — FILE MISSING: {}", name, path)

    logger.info("GeoJSON validation complete.")


# ---------------------------------------------------------------------------
# PostGIS seeding
# ---------------------------------------------------------------------------

def seed_postgis() -> None:
    """Seed lease boundaries into PostGIS using GeoAlchemy2."""
    try:
        import geopandas as gpd
        from sqlalchemy import create_engine, text
        from geoalchemy2 import Geometry  # noqa: F401 — registers types
    except ImportError as e:
        logger.error("Missing dependency for PostGIS seeding: {}", e)
        return

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL not set — skipping PostGIS seed.")
        return

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT PostGIS_Version()"))
        logger.success("PostGIS connection established.")
    except Exception as e:
        logger.error("PostGIS connection failed: {}. Falling back to GeoJSON mode.", e)
        return

    # Seed lease boundaries
    lease_path = Path(__file__).resolve().parents[1] / "config" / "lease_boundaries" / "jharkhand_sample.geojson"
    if not lease_path.exists():
        logger.error("Lease boundary file not found: {}", lease_path)
        return

    gdf = gpd.read_file(str(lease_path))
    gdf = gdf.to_crs("EPSG:4326")

    try:
        gdf.to_postgis(
            name="lease_boundaries",
            con=engine,
            if_exists="replace",
            index=False,
            dtype={"geometry": Geometry("POLYGON", srid=4326)},
        )
        logger.success("Seeded {} lease boundary records into PostGIS.", len(gdf))
    except Exception as e:
        logger.error("Failed to seed lease boundaries: {}", e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the mining detection database.")
    parser.add_argument(
        "--geojson-only",
        action="store_true",
        help="Only validate GeoJSON files, skip PostGIS.",
    )
    args = parser.parse_args()

    logger.info("=== Database Seed Script ===")
    seed_geojson()

    if not args.geojson_only:
        seed_postgis()
    else:
        logger.info("--geojson-only flag set — skipping PostGIS seed.")

    logger.info("=== Seed complete ===")


if __name__ == "__main__":
    main()
