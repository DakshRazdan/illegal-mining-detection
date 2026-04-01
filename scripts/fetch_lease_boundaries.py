"""
scripts/fetch_lease_boundaries.py
Fetches REAL mining boundaries from OpenStreetMap Overpass API.
Tags used: landuse=quarry, industrial=mine, landuse=mining

Run with:
    .venv\Scripts\python.exe scripts/fetch_lease_boundaries.py

Saves to:
    config/lease_boundaries/jharkhand.geojson
    config/lease_boundaries/odisha.geojson
    config/lease_boundaries/chhattisgarh.geojson
"""

import json
import time
import requests
from pathlib import Path

OUTPUT_DIR = Path("config/lease_boundaries")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OVERPASS_URL = "http://overpass-api.de/api/interpreter"

REGIONS = {
    "jharkhand": {
        "bbox": (23.0, 85.5, 24.5, 87.0),  # (min_lat, min_lon, max_lat, max_lon)
        "label": "Jharkhand Coal Belt",
    },
    "odisha": {
        "bbox": (20.0, 84.0, 21.5, 86.0),
        "label": "Odisha Mining Region",
    },
    "chhattisgarh": {
        "bbox": (21.5, 81.5, 23.0, 83.5),
        "label": "Chhattisgarh Coal Belt",
    },
}


def build_query(min_lat, min_lon, max_lat, max_lon):
    return f"""
[out:json][timeout:60];
(
  way["landuse"="quarry"]({min_lat},{min_lon},{max_lat},{max_lon});
  way["landuse"="mining"]({min_lat},{min_lon},{max_lat},{max_lon});
  way["industrial"="mine"]({min_lat},{min_lon},{max_lat},{max_lon});
  way["industrial"="quarry"]({min_lat},{min_lon},{max_lat},{max_lon});
  relation["landuse"="quarry"]({min_lat},{min_lon},{max_lat},{max_lon});
  relation["landuse"="mining"]({min_lat},{min_lon},{max_lat},{max_lon});
  node["industrial"="mine"]({min_lat},{min_lon},{max_lat},{max_lon});
);
out geom;
"""


def elements_to_geojson(elements, region_label):
    features = []

    for el in elements:
        props = {
            "osm_id":     el.get("id"),
            "osm_type":   el.get("type"),
            "region":     region_label,
            "name":       el.get("tags", {}).get("name", "Unknown Mine"),
            "landuse":    el.get("tags", {}).get("landuse", ""),
            "industrial": el.get("tags", {}).get("industrial", ""),
            "operator":   el.get("tags", {}).get("operator", ""),
            "mineral":    el.get("tags", {}).get("mineral", "coal"),
            "status":     "approved",  # OSM tagged = known/mapped mine
        }

        geometry = el.get("geometry", [])
        el_type  = el.get("type")

        if el_type == "node":
            lat = el.get("lat")
            lon = el.get("lon")
            if lat and lon:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": props,
                })

        elif el_type == "way" and geometry:
            coords = [[n["lon"], n["lat"]] for n in geometry if "lon" in n and "lat" in n]
            if len(coords) >= 3:
                # Close the polygon if not already closed
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": props,
                })

        elif el_type == "relation":
            # For relations, use the outer members' geometry
            members = el.get("members", [])
            for member in members:
                if member.get("role") == "outer" and member.get("geometry"):
                    coords = [[n["lon"], n["lat"]] for n in member["geometry"]
                              if "lon" in n and "lat" in n]
                    if len(coords) >= 3:
                        if coords[0] != coords[-1]:
                            coords.append(coords[0])
                        features.append({
                            "type": "Feature",
                            "geometry": {"type": "Polygon", "coordinates": [coords]},
                            "properties": props,
                        })
                        break

    return {"type": "FeatureCollection", "features": features}


def fetch_region(region_key, region_config):
    bbox     = region_config["bbox"]
    label    = region_config["label"]
    out_file = OUTPUT_DIR / f"{region_key}.geojson"

    print(f"\nFetching {label}...")
    print(f"  BBox: {bbox}")

    query = build_query(*bbox)

    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=90,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        data     = response.json()
        elements = data.get("elements", [])

        print(f"  Found {len(elements)} OSM elements")

        geojson = elements_to_geojson(elements, label)
        n       = len(geojson["features"])

        out_file.write_text(json.dumps(geojson, indent=2))
        print(f"  Saved {n} features → {out_file}")
        return n

    except requests.exceptions.Timeout:
        print(f"  TIMEOUT — Overpass is slow, try again in a few minutes")
        return 0
    except Exception as e:
        print(f"  ERROR: {e}")
        return 0


def merge_all():
    """Merge all 3 region files into one combined GeoJSON."""
    all_features = []
    for region_key in REGIONS:
        f = OUTPUT_DIR / f"{region_key}.geojson"
        if f.exists():
            data = json.loads(f.read_text())
            all_features.extend(data.get("features", []))

    combined = {"type": "FeatureCollection", "features": all_features}
    out = OUTPUT_DIR / "india_coal_belt.geojson"
    out.write_text(json.dumps(combined, indent=2))
    print(f"\nCombined: {len(all_features)} total features → {out}")


if __name__ == "__main__":
    print("=" * 50)
    print("OpenMine — Real Mining Boundary Fetcher")
    print("Source: OpenStreetMap Overpass API")
    print("=" * 50)

    total = 0
    for key, config in REGIONS.items():
        n = fetch_region(key, config)
        total += n
        time.sleep(2)  # be polite to Overpass

    merge_all()

    print("\n" + "=" * 50)
    print(f"Done. {total} real mining boundaries saved.")
    print("Files in config/lease_boundaries/")
    print("=" * 50)