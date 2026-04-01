from src.ingest.temporal_fetch import fetch_ndvi_composite

periods = [
    ("2023-01-01", "2023-03-31", "Q1 2023"),
    ("2024-01-01", "2024-03-31", "Q1 2024"),
    ("2024-07-01", "2024-09-30", "Q3 2024"),
]

for s, e, l in periods:
    print(f"Fetching {l}...")
    r = fetch_ndvi_composite(s, e, l)
    print(f"  {r['status']} — {r.get('scene_date', 'N/A')}")