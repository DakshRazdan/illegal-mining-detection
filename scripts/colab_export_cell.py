# ═══════════════════════════════════════════════════════════════════════════
# OPENMINE — COLAB → DASHBOARD BRIDGE
# Paste this cell at the END of your Colab notebook and run it.
# It packages all computed arrays and pushes them to your Railway server.
# ═══════════════════════════════════════════════════════════════════════════

import numpy as np
import requests

# ── 1. PACK ALL ARRAYS ─────────────────────────────────────────────────────
# Uses mining_score_v2 (6-index) if available, else mining_score (4-index).
# `dates` is a list of datetime objects from the temporal analysis loop.
# `scores` is a list of float mean scores per year.

_payload = dict(
    ndvi_a          = ndvi_a,
    ndvi_b          = ndvi_b,
    bsi_a           = bsi_a,
    bsi_b           = bsi_b,
    ndwi_a          = ndwi_a,
    ndwi_b          = ndwi_b,
    nbr_a           = nbr_a,
    nbr_b           = nbr_b,
    mining_score    = mining_score,
    temporal_dates  = np.array([str(d.year) for d in dates]),
    temporal_scores = np.array(scores, dtype=np.float32),
    affected_area_ha= np.float32(affected_area),
    peak_score      = np.float32(float(mining_score.max())),
)

# Add 6-index score + critical area only if extended analysis was run
try:
    _payload["mining_score_v2"]  = mining_score_v2
    _payload["critical_area_ha"] = np.float32(critical)
    _payload["peak_score"]       = np.float32(float(mining_score_v2.max()))
    print("✓ 6-index mining_score_v2 included")
except NameError:
    print("⚠  mining_score_v2 not found — using 4-index score only")

# ── 2. SAVE TO /tmp ────────────────────────────────────────────────────────
_npz_path = "/tmp/openmine_payload.npz"
np.savez_compressed(_npz_path, **_payload)

import os
_size_kb = os.path.getsize(_npz_path) / 1024
print(f"✓ Saved {_npz_path}  ({_size_kb:.1f} KB)")
print(f"  Arrays packed: {list(_payload.keys())}")

# ── 3. PUSH TO RAILWAY DASHBOARD ──────────────────────────────────────────
DASHBOARD_URL = "https://web-production-f8923.up.railway.app"

print(f"\nUploading to {DASHBOARD_URL}/api/colab/ingest ...")
with open(_npz_path, "rb") as _f:
    _resp = requests.post(
        f"{DASHBOARD_URL}/api/colab/ingest",
        files={"file": ("openmine_payload.npz", _f, "application/octet-stream")},
        timeout=60,
    )

if _resp.status_code == 200:
    _data = _resp.json()
    print(f"\n✅ Ingest successful!")
    print(f"   Loaded keys : {_data['loaded_keys']}")
    print(f"   Array shape : {_data['shape']}")
    print(f"   Message     : {_data['message']}")
    print(f"\n🗺  Dashboard live at: {DASHBOARD_URL}")
else:
    print(f"\n❌ Ingest failed — HTTP {_resp.status_code}")
    print(_resp.text)

# ── 4. VERIFY STATUS ──────────────────────────────────────────────────────
_status = requests.get(f"{DASHBOARD_URL}/api/colab/status", timeout=10).json()
print(f"\n📊 Server status:")
print(f"   Colab loaded  : {_status['loaded']}")
print(f"   Available keys: {_status['available_keys']}")
print(f"   Array shape   : {_status['array_shape']}")
print(f"   Affected area : {_status.get('affected_area_ha')} ha")
print(f"   Peak score    : {_status.get('peak_score')}")