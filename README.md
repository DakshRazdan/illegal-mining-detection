Autonomous Illegal Mining Detection System (AIMDS)

An end-to-end agentic remote sensing pipeline for real-time detection and regulatory verification of unauthorized mining activity.


Overview
AIMDS extends conventional satellite change-detection by introducing an autonomous verification loop. Each detected excavation anomaly is programmatically cross-referenced against three authoritative regulatory datasets before any alert is issued:

State Mining Leases — Determines whether the detected activity falls within a registered mine boundary.
Environmental Clearances (MoEFCC) — Validates whether an applicable lease holds a current, non-expired Environmental Clearance.
Land Records — Flags activity occurring within protected forest zones or scheduled tribal land.

Alerts are dispatched via Twilio (WhatsApp/SMS) to the concerned District Magistrate exclusively when the system classifies a detection as both verified illegal and CRITICAL risk. This design eliminates false-positive fatigue and ensures that every notification represents actionable intelligence.

Technology Stack
LayerLibraries & ToolsAI / MLPyTorch, segmentation-models-pytorch (U-Net), Ultralytics YOLOv11, scikit-learnGeospatialpystac-client, rasterio, GeoPandas, Sentinel-2 L2A STAC, Sentinel-1 SARBackendFastAPI, Uvicorn, PostgreSQL + PostGIS (Docker)FrontendVanilla WebGL / Three.js, Jinja2 Templates, Tailwind CSS
The frontend is rendered server-side via Python Jinja2 templates and requires no Node.js runtime.

Quickstart — Synthetic Demo Mode
A synthetic data generator is included to demonstrate the complete verification pipeline and 3D command dashboard without requiring GPU hardware or satellite imagery downloads.
Step 1 — Install dependencies
bashpip install -r requirements.txt
Step 2 — Generate synthetic detections and run the verification pipeline
bashpython scripts/demo.py --synthetic
This script simulates a multi-band Sentinel-2 acquisition over Jharkhand, generates randomised detections, runs them through the full regulatory verification workflow, scores each detection, and writes the output to disk.
Step 3 — Launch the command dashboard
bashuvicorn src.dispatch.dashboard_api:app --reload --port 5000
```

Navigate to [http://127.0.0.1:5000/](http://127.0.0.1:5000/) to access the interactive 3D dashboard, real-time telemetry panel, and live verification feed.

---

## System Architecture
```
Ingest → Detect → Verify → Dispatch
StageModuleDescriptionIngestsrc/ingestRetrieves bi-temporal 7-band Sentinel-2 image stacks via Microsoft Planetary Computer STACDetectsrc/detectEnsemble fusion of Spectral Random Forest anomaly detection, U-Net semantic segmentation, and YOLOv11 object detectionVerifysrc/verifyAutonomous agent cross-references detections against lease_boundaries/jharkhand_sample.geojson and ec_records.jsonDispatchsrc/dispatchFormats high-risk verified detections into structured alerts; FastAPI exposes results as a JSON API

Acknowledgements
Developed for Hackathon 2026.
