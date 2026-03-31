# EXECUTION_PLAN.md — Phase-by-Phase Build Instructions
# Illegal Mining Detection System
# READ THIS alongside SPEC.md before starting any phase

---

## Phase 1 — Initialization ✅

**Owner: Antigravity Agent 1 (Scaffold)**

Tasks:
- [x] Verify repo structure against SPEC.md
- [x] Create all missing directories
- [x] Create requirements.txt
- [x] Create .env.example
- [x] Create docker-compose.yml (PostGIS + pgAdmin)
- [x] Create config/ (settings.yaml, aoi.geojson, ec_records.json, land_records.json, lease_boundaries/)
- [x] Create src/types.py (shared typed data structures)
- [x] Create src/utils/ (logger.py, config.py, geo_utils.py)
- [x] Create scripts/init_db.sql (PostGIS schema)
- [x] Create scripts/seed_db.py
- [x] Create scripts/demo.py (with --synthetic flag)
- [x] Create CHANGELOG.md

**Verify with:**
```
python scripts/seed_db.py --geojson-only
python scripts/demo.py --synthetic
```

---

## Phase 2 — Blueprint

**Owner: Antigravity (planning) + Claude Code Terminals (implementation plan review)**

Tasks:
- [ ] Implementation Plan artifact — full architecture
- [ ] AI Architecture artifact — data flow diagram
- [ ] Wait for user approval before any Phase 3 work

---

## Phase 3 — Link (Data Layer)

**Owner: Split (see SPEC.md terminal assignments)**

### Claude Code Terminal 1 — Ingest + Preprocess
Prompt:
> Implement src/ingest/sentinel2.py using the pre-validated STAC code from SPEC.md.
> Implement src/preprocess/cloud_mask.py for cloud masking.
> Target AOI: 85.8-86.2 lon, 23.5-23.8 lat, EPSG 32645.
> Do NOT modify any other files.

### Claude Code Terminal 2 — Verification
Prompt:
> Implement src/verify/lease_check.py, src/verify/ec_check.py, src/verify/risk_score.py,
> and src/verify/verifier.py. Input: list[DetectionResult] from src/types.py.
> Use GeoJSON fallback (config/lease_boundaries/) if PostGIS unavailable.
> Do NOT modify detection or dashboard code.

### Antigravity Agent 3 — Dispatch
- [ ] Implement src/dispatch/alerter.py (Twilio WhatsApp + SMS + console fallback)
- [ ] Implement src/dispatch/dashboard_api.py (Flask API endpoints)

---

## Phase 4 — Architect (Core Features)

### Claude Code Terminal 1 — ML Models (Agent Prompt 4.3)
Prompt:
> src/detect/spectral_rf.py is ALREADY IMPLEMENTED — do NOT rewrite it.
> It uses a 7-band stack (B03, B04, B05, B07, B08, B11, B12) and 6-index v2 fusion
> (NDVI, BSI, NDWI, NBR, CMI, RECI). Treat it as a dependency, not a task.
> Implement src/detect/unet_detect.py with U-Net inference (fallback to stub if no weights).
> Implement src/detect/ensemble.py to fuse spectral_rf + unet + yolo outputs.
> Ingestion in src/ingest/sentinel2.py MUST request 7 bands:
>   assets=["B04", "B08", "B11", "B03", "B05", "B07", "B12"]

### Antigravity Agent 2 — Detection Integration
- [ ] Wire src/detect/ outputs into PipelineResult via src/types.py
- [ ] Integrate ensemble results with verification pipeline

### Antigravity Agent 4 — Dashboard
- [ ] Implement dashboard/map.py (Folium dark satellite map)
- [ ] Implement dashboard/app.py (Flask server)
- [ ] Implement scripts/generate_dashboard.py

---

## Phase 5 — Stylize

**Owner: Antigravity Agent 4 (Frontend)**

- [ ] Apply ISRO mission control theme across dashboard
- [ ] Glass panels, saffron/green India color system
- [ ] 3D risk gauge (CSS or Chart.js fallback)
- [ ] Glowing polygon overlays on map
- [ ] Full browser QA

---

## Phase 6 — Trigger (Demo Hardening)

**Owner: All agents**

- [ ] `python scripts/demo.py --synthetic` runs clean, no errors
- [ ] README.md polished — impresses judge in 30 seconds
- [ ] CHANGELOG.md complete
- [ ] No console errors in demo mode
- [ ] WhatsApp alert demonstrable (console print fallback)
- [ ] Docker: `docker compose up` starts PostGIS cleanly

---

## Claude Code Handoff Blocks

### Terminal 1 — Sentinel-2 Ingestion

```
CLAUDE CODE HANDOFF
Terminal: 1
Task: Implement Sentinel-2 STAC ingestion and preprocessing
Files: src/ingest/sentinel2.py, src/preprocess/cloud_mask.py
Prompt:
> Read SPEC.md for the pre-validated STAC ingestion code.
> Copy it exactly into src/ingest/sentinel2.py. Do NOT modify the logic.
> Add cloud masking in src/preprocess/cloud_mask.py using the SCL band.
> All imports must work within the existing .venv. No new installs.
> Output: writes processed rasters to data/processed/
```

### Terminal 2 — Verification Logic

```
CLAUDE CODE HANDOFF
Terminal: 2
Task: Implement verification layer
Files: src/verify/lease_check.py, src/verify/ec_check.py, src/verify/risk_score.py, src/verify/verifier.py
Prompt:
> Read SPEC.md and src/types.py.
> Input: list[DetectionResult]. Output: list[VerificationResult].
> Use GeoJSON from config/lease_boundaries/ — PostGIS optional.
> Risk score uses weights from config/settings.yaml risk section.
> No ML code, no frontend code.
```

### Terminal 3 — Test Coverage

```
CLAUDE CODE HANDOFF
Terminal: 3
Task: Write pytest test suite
Files: tests/test_lease_check.py, tests/test_risk_score.py, tests/test_pipeline.py
Prompt:
> Read src/types.py and src/utils/ first.
> Write pytest tests for: lease_check (inside/outside/expired leases),
> risk_score (CRITICAL/HIGH/MEDIUM/LOW thresholds), and
> synthetic pipeline (demo.py --synthetic runs without error).
> All tests must pass with: pytest tests/ -v
```
