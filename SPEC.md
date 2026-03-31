# SPEC.md — Agent Specification Document
# [PROJECT_NAME] — Autonomous Illegal Mining Detection System
# Last Updated: March 31, 2026
# READ THIS BEFORE EVERY TASK. DO NOT SKIP.

---

## What You Are Building

An autonomous illegal mining detection system for India. Uses satellite imagery
(Sentinel-2 optical, Sentinel-1 SAR, NISAR L-band) to detect mining activity,
then autonomously verifies whether detected mining is legal or illegal by
cross-referencing mining lease boundaries, environmental clearances, and land
records. Only verified illegal activity triggers alerts to district magistrates
via WhatsApp/SMS.

The core differentiator: Zero-Latency Agentic Verification Loop.
The system does not just detect a hole in the ground — it checks if that hole
is legal before alerting a human.

---

## Stack (Non-Negotiable)

- Language: Python 3.11+
- ML: PyTorch, segmentation-models-pytorch (U-Net), Ultralytics (YOLOv11), scikit-learn
- Geospatial: GDAL, rasterio, geopandas, shapely, pyproj
- Database: PostGIS (via Docker), SQLAlchemy, GeoAlchemy2
- Satellite APIs: pystac-client, planetary-computer, asf-search, sentinelsat
- Alerts: Twilio (WhatsApp + SMS)
- Dashboard: Folium (primary), Flask (API server)
- Config: python-dotenv, PyYAML
- All secrets via .env only. Never hardcode credentials.

---

## Project Structure

root/
├── SPEC.md                  ← you are here
├── EXECUTION_PLAN.md        ← phase-by-phase build instructions
├── WHITEPAPER.md            ← technical rationale
├── README.md                ← written last, for humans
├── CHANGELOG.md             ← agents append here after every task
├── .env                     ← secrets, never commit
├── docker-compose.yml
├── requirements.txt
├── config/
│   ├── aoi.geojson
│   ├── settings.yaml
│   ├── ec_records.json
│   ├── land_records.json
│   └── lease_boundaries/
├── src/
│   ├── ingest/              ← owned by Claude Code Terminal 1
│   ├── preprocess/          ← owned by Claude Code Terminal 1
│   ├── detect/              ← owned by Claude Code Terminal 1
│   ├── verify/              ← owned by Claude Code Terminal 2
│   ├── dispatch/            ← owned by Antigravity API Agent
│   └── utils/
├── training/                ← owned by Claude Code Terminal 1
├── models/
├── data/
├── dashboard/               ← owned by Antigravity Frontend Agent
├── scripts/
├── results/
└── tests/                   ← owned by Claude Code Terminal 3

---

## Agent Responsibilities

### Antigravity — Agent 1: Scaffold + Database Agent
Owns: root config, docker-compose.yml, scripts/seed_db.py, PostGIS schema
Job: Project scaffold, directory structure, DB setup, config files
Output: Running PostGIS, seeded lease boundaries, all directories created
Never touch: ML code, frontend, detection logic

### Antigravity — Agent 2: Detection Agent
Owns: src/detect/, src/preprocess/
Job: U-Net segmentation, YOLO machinery detection, RF spectral anomaly, ensemble fusion
Input: Processed rasters from src/ingest/
Output: List of DetectionResult objects
Never touch: frontend, database, alerts

### Antigravity — Agent 3: Verification + Dispatch Agent
Owns: src/verify/, src/dispatch/
Job: Lease check, EC check, land records, risk scoring, WhatsApp/SMS alerts
Input: DetectionResult objects from detection layer
Output: Verdict dicts, alerts dispatched, saved to DB
Never touch: ML models, data ingestion, frontend

### Antigravity — Agent 4: Frontend + Dashboard Agent
Owns: dashboard/, scripts/generate_dashboard.py, src/dispatch/dashboard_api.py
Job: Folium map, Flask API, demo script
Input: Results from PostGIS via API
Output: results/demo/dashboard.html, running Flask server
Never touch: ML code, database schema, detection logic

---

## Claude Code Terminal Assignments

These tasks are NEVER handled by Antigravity agents.
When Antigravity hits one of these, it STOPS and outputs a CLAUDE CODE HANDOFF block.

### Terminal 1 — Data + ML Pipeline
Owns: src/ingest/, src/preprocess/, training/
- Sentinel-2 ingestion via pystac-client + planetary-computer
- Sentinel-1 ingestion via asf-search
- Cloud masking, SAR calibration, band fusion
- U-Net training pipeline (download_iiasa, prepare_iiasa, train_unet)
- YOLO training placeholder
- RF spectral classifier training

### Terminal 2 — Verification Logic
Owns: src/verify/
- Lease boundary spatial queries (PostGIS + GeoJSON fallback)
- EC records check
- Land records check
- Risk scoring algorithm
- Verification agent orchestrator

### Terminal 3 — Test Coverage
Owns: tests/
- pytest for all Python modules
- test_lease_check.py, test_risk_score.py, test_pipeline.py
- Run after every Antigravity agent completes a task

---

## Claude Code Handoff Protocol

When an Antigravity agent hits a task owned by a Claude Code terminal:
1. STOP immediately
2. Do NOT write placeholder code
3. Output this exact block:

CLAUDE CODE HANDOFF
Terminal: [1 / 2 / 3]
Task: [exact description]
Files involved: [list]
Prompt:
> [ready-to-paste Claude Code instruction]

4. Move to your next task

---

## Data Flow

Satellite APIs
    ↓
src/ingest/          (Claude Code T1)
    ↓
src/preprocess/      (Claude Code T1)
    ↓
src/detect/          (Antigravity Agent 2)
    ↓  DetectionResult objects
src/verify/          (Claude Code T2)
    ↓  Verdict dicts
src/dispatch/        (Antigravity Agent 3)
    ↓
PostGIS + Twilio + Folium Dashboard

Cross-agent data flows ONLY through:
- src/data/ directory (files on disk)
- PostGIS database
- Never direct function calls across agent boundaries

---

## File Ownership Rules

- No agent writes outside its owned directories
- If unsure which directory owns a file, check this SPEC before writing
- CHANGELOG.md: every agent appends after completing any task
- .env: never modify, only read via python-dotenv
- SPEC.md: never modify, only read

---

## CHANGELOG Protocol

After completing any task, append to CHANGELOG.md:

[DATE TIME] — [Agent Name]
- Task completed: [description]
- Files created/modified: [list]
- Next recommended task: [description]

---

## Demo Mode

If trained model weights do not exist (models/unet/best.pth):
- Use --synthetic flag in scripts/demo.py
- Generates 8-12 fake DetectionResult objects across AOI
- Some inside lease boundaries (legal), some outside (illegal)
- Demo must work end-to-end without real model weights

Priority order if time runs out:
1. Never skip Verification Agent — it is the differentiating feature
2. Skip D-InSAR, use coherence stub
3. Skip SAR fusion, use optical-only
4. Skip React dashboard, use Folium
5. Use --synthetic if no GPU for training

---

## Key Reference Files

- EXECUTION_PLAN.md — exact agent prompts per phase, copy-paste into Agent Manager
- WHITEPAPER.md — technical rationale, algorithm descriptions, data sources
- config/settings.yaml — all thresholds, weights, API URLs
- config/aoi.geojson — Jharkhand AOI boundary
- config/lease_boundaries/jharkhand_sample.geojson — sample lease polygons