# CHANGELOG

All notable changes to the Illegal Mining Detection System are documented here.
Format: `[DATE TIME] — [Agent Name]`

---

## [2026-03-31 12:02 IST] — Antigravity Agent 1 (Scaffold)

- Task completed: Phase 1 Initialization — full directory scaffold
- Files created: CHANGELOG.md, requirements.txt, .env.example, docker-compose.yml,
  config/settings.yaml, config/aoi.geojson, config/ec_records.json,
  config/land_records.json, config/lease_boundaries/jharkhand_sample.geojson,
  src/__init__.py + all subdirectory __init__.py files,
  src/utils/logger.py, src/utils/geo_utils.py,
  scripts/seed_db.py, scripts/demo.py, EXECUTION_PLAN.md, WHITEPAPER.md
- Next recommended task: Phase 2 Blueprint — Implementation Plan + AI Architecture artifacts

---

## [2026-03-31 12:18 IST] — Antigravity Agent 2 (Detection)

- Task completed: Updated spectral detection to 6-index fusion (added CMI + RECI)
- Files modified: src/detect/spectral_rf.py (created), EXECUTION_PLAN.md (Agent Prompt 4.3 updated)
- Changes:
  - Bands updated: 4-band → 7-band stack (added B05, B07, B12)
  - compute_indices() → compute_indices_extended() (adds CMI + RECI indices)
  - Mining score weights updated to v2: NDVI(0.25) BSI(0.20) NDWI(0.15) NBR(0.15) CMI(0.15) RECI(0.10)
  - EXECUTION_PLAN.md Agent Prompt 4.3 updated to reflect 7-band stack requirement for ingestion
- Next recommended task: Phase 2 Blueprint artifacts

---

## [2026-03-31 14:45 IST] — Gemini (Taking over all agents)

- Task completed: Phase 4 & Phase 5 Execution (Link, Architect, Stylize, Trigger)
- Files created/modified: `src/ingest/sentinel2.py`, `src/ingest/sentinel1.py`, `src/preprocess/cloud_mask.py`, `src/verify/lease_check.py`, `src/verify/ec_check.py`, `src/verify/risk_score.py`, `src/verify/verifier.py`, `src/detect/unet_detect.py`, `src/detect/yolo_detect.py`, `src/detect/ensemble.py`, `src/dispatch/dashboard_api.py`, `dashboard/templates/index.html`, `dashboard/static/style.css`, `dashboard/static/script.js`, `README.md`
- Next recommended task: Hackathon Submission!

---

## [2026-03-31 15:05 IST] — Gemini

- Task completed: Fixed Folium map UI anomalies (tiles, custom legend, header styling, marker opacity)
- Files modified: `dashboard/map.py`

---

## [2026-03-31 15:30 IST] — Gemini

- Task completed: Integrated Planetary Computer Temporal Slider & Light Theme Pivot
- Feature details: 
  - Dynamic fetching of Sentinel-2 NDVI composites across 12 periods.
  - Injected Leaflet `L.imageOverlay` opacity scrubbing into the Folium map.
  - Implemented Light Mode base theme (`light_all`) with optimized marker contrast.
  - Refactored header to prevent CSS/JS text selection bugs.
- Files created/modified: `src/ingest/temporal_fetch.py`, `scripts/prefetch_temporal.py`, `src/dispatch/dashboard_api.py`, `dashboard/map.py`
