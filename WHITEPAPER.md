# WHITEPAPER.md — Technical Rationale
# Illegal Mining Detection System — Jharkhand, India
# Version 1.0 | March 2026

---

## Problem Statement

Illegal mining in India causes an estimated ₹50,000 crore in annual revenue loss to the state,
destroys forest cover, contaminates water bodies, and displaces tribal communities. Despite
laws like MMDR Act 1957 (amended 2021) and Forest Conservation Act, enforcement is reactive
— inspectors are dispatched only after complaints, often weeks after illegal activity begins.

**This system automates satellite-based monitoring and legal cross-checking, reducing
detection-to-action latency from weeks to hours.**

---

## Core Differentiator: Zero-Latency Agentic Verification Loop

Most remote sensing tools stop at detection — they show you a change, not its legality.
This system runs every detection through an automated verification chain:

```
Detection → Lease Boundary Check → EC Status Check → Land Records Check
→ Risk Score → Alert Dispatch (only if ILLEGAL)
```

A district magistrate only receives an alert when all three checks confirm illegality.
False alarm rate target: < 5%.

---

## Algorithm Architecture

### 1. Satellite Ingestion

**Primary**: Sentinel-2 L2A (10m optical, freely available via Microsoft Planetary Computer)
**Secondary**: Sentinel-1 GRD (SAR, all-weather, 10m)
**Future**: NISAR L-band (2025+, 3m, NASA-ISRO)

**Bands used** (60m for change detection speed):
- B04 (Red), B08 (NIR), B11 (SWIR), B03 (Green)

### 2. Spectral Change Detection

Bi-temporal change analysis between a baseline period (2019) and monitoring period (2023).

**Spectral Indices:**
- NDVI — Normalized Difference Vegetation Index (vegetation cover loss)
- BSI — Bare Soil Index (bare earth exposure — key mining signal)
- NDWI — Normalized Difference Water Index (water disturbance)
- NBR — Normalized Burn Ratio (soil/vegetation change proxy)

**Mining Score (validated weights):**
```
mining_score = 0.35 × ΔNDVI + 0.30 × ΔBSI + 0.20 × ΔNDWI + 0.15 × ΔNBR
```

Threshold: 0.5 → pixel classified as mining-altered

### 3. False Positive Filtering

OpenStreetMap Overpass API filters out known residential, farmland, and industrial areas
before reporting detections. This is critical for urban-adjacent mining regions.

### 4. Land Cover Classification (K-Means)

4-class unsupervised K-Means on (NDVI, BSI, NDWI, NBR) feature space:
- Forest (high NDVI)
- Mining (high BSI)
- Water (high NDWI)
- Degraded / bare (residual)

No labeled training data required — works on any AOI out of the box.

### 5. U-Net Segmentation (optional, for higher accuracy)

Trained on IIASA Global Land Cover dataset with mining-site annotations.
Input: 4-band Sentinel-2 tile (256×256 pixels)
Output: Binary mining probability mask
Fallback: Spectral RF if weights not available.

### 6. Verification Layer

**Lease Check** (PostGIS spatial query / GeoJSON fallback):
- Is the detected location inside any known mining lease polygon?
- Is the lease ACTIVE or EXPIRED?

**Environmental Clearance Check**:
- Does the lease have a valid MoEFCC/State PCB clearance?
- Is the clearance within its valid date range?

**Land Records Check**:
- Is it forest land? Tribal land? Government land?
- Are there additional restrictions?

**Risk Score Formula:**
```
base_score = mining_score × 100
+ 40 (if outside all leases)
+ 30 (if no valid EC)
+ 20 (if on forest/tribal land)
clamped to [0, 100]
```

Risk Level:
- CRITICAL ≥ 80: Immediate WhatsApp alert to DM
- HIGH ≥ 60: WhatsApp + SMS alert
- MEDIUM ≥ 40: Log only (district office follow-up)
- LOW < 40: No action

---

## Data Sources

| Source | Type | Resolution | Latency | Cost |
|--------|------|-----------|---------|------|
| Sentinel-2 L2A (PC) | Optical | 10-60m | 3-5 days | Free |
| Sentinel-1 GRD | SAR | 10m | 1-3 days | Free |
| OSM Overpass | Vector | N/A | Real-time | Free |
| Jharkhand Lease Registry | Vector | N/A | Static | Gov API |
| MoEFCC EC Database | Records | N/A | Static | Web scrape |

---

## Legal Framework

- Mines and Minerals (Development and Regulation) Act, 1957 (MMDR)
- Forest Conservation Act, 1980
- Environment Protection Act, 1986
- Panchayats Extension to Scheduled Areas (PESA) Act, 1996 (tribal rights)
- National Green Tribunal Orders on mining in Jharkhand

---

## Scalability

The pipeline is AOI-agnostic. To extend to a new state:
1. Update `config/aoi.geojson` with the new bounding box
2. Add lease boundary GeoJSON to `config/lease_boundaries/`
3. Update EC records in `config/ec_records.json`
4. Re-run `scripts/seed_db.py`

No model retraining required for spectral detection (indices are universal).
U-Net may need fine-tuning for different mining types (quarry vs. coal vs. sand).

---

## Demo Mode (--synthetic)

For live demos without GPU or real satellite data:
- 8-12 synthetic DetectionResult objects generated across Jharkhand AOI
- ~40% placed outside lease boundaries (triggers CRITICAL/HIGH alerts)
- ~60% placed inside active leases (LOW/legal — suppressed)
- Full verification + dispatch pipeline runs on synthetic data
- Demonstrates the agentic loop end-to-end in < 10 seconds
