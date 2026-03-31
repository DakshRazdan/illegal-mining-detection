"""
src/utils/geo_utils.py — Shared geospatial helpers.
Wraps shapely / geopandas / pyproj for use across all pipeline modules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
from pyproj import Transformer
from shapely.geometry import Point, Polygon, shape
from shapely.ops import transform

from src.utils.logger import logger


# ---------------------------------------------------------------------------
# GeoJSON helpers
# ---------------------------------------------------------------------------

def load_geojson(path: str | Path) -> gpd.GeoDataFrame:
    """Load a GeoJSON file into a GeoDataFrame (EPSG:4326)."""
    gdf = gpd.read_file(str(path))
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
    logger.debug("Loaded GeoJSON: {} ({} features)", path, len(gdf))
    return gdf


def load_aoi(aoi_path: str | Path | None = None) -> dict[str, Any]:
    """Return AOI as a GeoJSON-style dict (Polygon geometry)."""
    if aoi_path is None:
        aoi_path = Path(__file__).resolve().parents[2] / "config" / "aoi.geojson"
    with open(aoi_path, "r") as f:
        fc = json.load(f)
    return fc["features"][0]["geometry"]


# ---------------------------------------------------------------------------
# Coordinate transforms
# ---------------------------------------------------------------------------

def wgs84_to_utm(lon: float, lat: float, epsg: int = 32645) -> tuple[float, float]:
    """Convert WGS84 lon/lat to UTM easting/northing."""
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    return transformer.transform(lon, lat)


def utm_to_wgs84(easting: float, northing: float, epsg: int = 32645) -> tuple[float, float]:
    """Convert UTM easting/northing to WGS84 lon/lat."""
    transformer = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    return transformer.transform(easting, northing)


# ---------------------------------------------------------------------------
# Spatial queries
# ---------------------------------------------------------------------------

def point_in_any_polygon(lon: float, lat: float, gdf: gpd.GeoDataFrame) -> bool:
    """Return True if (lon, lat) falls inside any polygon in gdf."""
    pt = Point(lon, lat)
    return bool(gdf.geometry.contains(pt).any())


def get_containing_feature(lon: float, lat: float, gdf: gpd.GeoDataFrame) -> dict | None:
    """Return properties dict of the first polygon containing the point, or None."""
    pt = Point(lon, lat)
    mask = gdf.geometry.contains(pt)
    if not mask.any():
        return None
    row = gdf[mask].iloc[0]
    return row.to_dict()


def bbox_to_polygon(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> Polygon:
    """Create a shapely Polygon from bounding box coords."""
    return Polygon([
        (min_lon, min_lat),
        (max_lon, min_lat),
        (max_lon, max_lat),
        (min_lon, max_lat),
        (min_lon, min_lat),
    ])


# ---------------------------------------------------------------------------
# Pixel ↔ coordinate mapping
# ---------------------------------------------------------------------------

def pixel_to_lonlat(
    row: int,
    col: int,
    min_lon: float,
    max_lon: float,
    min_lat: float,
    max_lat: float,
    height: int,
    width: int,
) -> tuple[float, float]:
    """Convert pixel (row, col) to geographic (lon, lat)."""
    lon = min_lon + (col / width) * (max_lon - min_lon)
    lat = max_lat - (row / height) * (max_lat - min_lat)
    return lon, lat


def mask_to_centroids(
    mask: np.ndarray,
    min_lon: float,
    max_lon: float,
    min_lat: float,
    max_lat: float,
) -> list[tuple[float, float]]:
    """Return (lon, lat) centroid list for each connected True region in mask."""
    from scipy import ndimage

    labeled, num_features = ndimage.label(mask)
    centroids = []
    h, w = mask.shape
    for i in range(1, num_features + 1):
        ys, xs = np.where(labeled == i)
        cy = float(np.mean(ys))
        cx = float(np.mean(xs))
        lon, lat = pixel_to_lonlat(cy, cx, min_lon, max_lon, min_lat, max_lat, h, w)
        centroids.append((lon, lat))
    return centroids


__all__ = [
    "load_geojson",
    "load_aoi",
    "wgs84_to_utm",
    "utm_to_wgs84",
    "point_in_any_polygon",
    "get_containing_feature",
    "bbox_to_polygon",
    "pixel_to_lonlat",
    "mask_to_centroids",
]
