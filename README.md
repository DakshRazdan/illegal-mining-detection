# 🛰️ Autonomous Illegal Mining Detection System (AIMDS)

> **Zero-Latency Agentic Verification Loop**
> Detecting a hole in the ground is easy. Knowing if it's legal in real-time is hard.
> 
> *Winner — Hackathon 2026*

---

## 🚀 The Differentiator
Most remote sensing systems stop at detection. **AIMDS** is an autonomous agentic system that doesn't just detect changes via satellite—it verifies them.

Every detected crater is automatically cross-referenced against:
1. **State Mining Leases:** Is this actually inside a registered mine?
2. **Environmental Clearances (MoEFCC):** If it is registered, does it have an active EC that hasn't expired?
3. **Land Records:** Is this protected forest or tribal land?

Only if the system mathematically proves the activity is **Illegal** and hits the `CRITICAL` risk threshold does it dispatch a live Twilio WhatsApp/SMS alert to the District Magistrate. False positives disappear. Actionable intelligence remains.

---

## 💻 Tech Stack
- **AI/ML Layer (Python):** `PyTorch`, `segmentation-models-pytorch` (U-Net), `ultralytics` (YOLOv11), `scikit-learn` (Spectral K-Means)
- **Geospatial (Python):** `pystac-client`, `rasterio`, `geopandas`, Sentinel-2 L2A STAC, Sentinel-1 SAR
- **Backend:** `FastAPI`, `Uvicorn`, PostgreSQL/PostGIS (Docker)
- **Frontend / Command Center:** Glassmorphic Vanilla WebGL / Three.js driven completely via Python Jinja Templates & Tailwind CSS. No Node.js required.

---

## ⚡ Quickstart (Demo Mode)

We built an end-to-end synthetic data generator so you can test the **entire verification pipeline and 3D dashboard** without downloading gigabytes of satellite imagery or needing a GPU.

**1. Install Dependencies**
```bash
pip install -r requirements.txt
```

**2. Generate Detections & Run Verification (Synthetic Demo)**
```bash
python scripts/demo.py --synthetic
```
*(This simulates Sentinel-2 data, generates random detections across Jharkhand, cross-checks them against GeoJSON leases, scores them, and writes the output).*

**3. Launch the ISRO Command Center Dashboard**
```bash
uvicorn src.dispatch.dashboard_api:app --reload --port 5000
```
Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/) in your browser.

> You will see a mesmerizing 3D wireframe globe, real-time telemetry, and a live verification feed filtering detections into *Illegal* and *Legal* categories.

---

## 🧠 Core Architecture Flow

1. **Ingest (`src/ingest`)** — Pulls bi-temporal 7-band Sentinel-2 stacks via Microsoft Planetary Computer STAC.
2. **Detect (`src/detect`)** — Ensemble weighted fusion. Spectral Random Forest anomalies form the baseline, reinforced by semantic deep learning (U-Net) and object detection (YOLOv11).
3. **Verify (`src/verify`)** — The autonomous agent checks `lease_boundaries/jharkhand_sample.geojson` and `ec_records.json`.
4. **Dispatch (`src/dispatch`)** — High-Risk items formatted into critical alerts. FastAPI serves the results via JSON. 

---

### *Built under extreme time pressure for Hackathon 2026.*
