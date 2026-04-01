# Illegal Mining Detection System — Jharkhand, India
## Technical Whitepaper · Version 1.0 · March 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [System Architecture](#3-system-architecture)
4. [Algorithm Design](#4-algorithm-design)
5. [Verification Layer](#5-verification-layer)
6. [Data Sources](#6-data-sources)
7. [Legal Framework](#7-legal-framework)
8. [Scalability & Extensibility](#8-scalability--extensibility)
9. [Demo Mode](#9-demo-mode)
10. [References](#10-references)

---

## 1. Executive Summary

This system provides automated, satellite-based detection of illegal mining activity in Jharkhand, India, integrated with real-time legal verification to reduce detection-to-action latency from weeks to hours. By combining multi-spectral change detection with automated lease, environmental clearance, and land records checks, the pipeline produces actionable intelligence — not raw detections — delivered directly to district magistrates only when illegality is confirmed.

**Target false alarm rate: < 5%.**

---

## 2. Problem Statement

Illegal mining in India causes an estimated ₹50,000 crore in annual revenue loss to the state. Beyond fiscal damage, it contributes to:

- Deforestation and loss of forest cover in ecologically sensitive zones
- Contamination of water bodies used by downstream communities
- Displacement of scheduled tribe communities with statutory land protections

Despite legislative safeguards under the MMDR Act 1957 (amended 2021) and the Forest Conservation Act 1980, enforcement remains reactive. Inspectors are typically dispatched only after complaints are filed, often weeks after illegal activity has commenced.

This system addresses that gap by automating continuous monitoring and legal cross-referencing across the entire area of interest (AOI), enabling authorities to act within hours of a detectable change.

---

## 3. System Architecture

### 3.1 Agentic Verification Loop

The core differentiator of this system is that detection and legal verification are tightly coupled in a single automated pipeline. Most remote sensing tools stop at detection — they surface a land-cover change without determining its legal status. This system runs every detection through a sequential verification chain before any alert is issued:

```
Satellite Ingestion
       │
       ▼
Spectral Change Detection
       │
       ▼
False Positive Filtering (OSM)
       │
       ▼
Land Cover Classification (K-Means / U-Net)
       │
       ▼
┌─────────────────────────────────┐
│       Verification Layer        │
│  ① Lease Boundary Check         │
│  ② Environmental Clearance (EC) │
│  ③ Land Records Check           │
└─────────────────────────────────┘
       │
       ▼
Risk Scoring
       │
       ▼
Alert Dispatch (only if ILLEGAL)
```

A district magistrate receives an alert only when all applicable checks confirm illegality. Detections that fall within valid, active leases are suppressed automatically.

---

## 4. Algorithm Design

### 4.1 Satellite Data Ingestion

| Stream | Source | Modality | Resolution | Availability |
|--------|--------|----------|------------|--------------|
| Primary | Sentinel-2 L2A (Microsoft Planetary Computer) | Optical | 10 m | Free |
| Secondary | Sentinel-1 GRD | SAR (all-weather) | 10 m | Free |
| Future | NISAR L-band | SAR | 3 m | NASA-ISRO (2025+) |

**Bands used for change detection** (60 m resampling for processing speed):

| Band | Description | Role |
|------|-------------|------|
| B04 | Red | Vegetation / NDVI |
| B08 | NIR | Vegetation / NDVI |
| B11 | SWIR | Bare soil / BSI |
| B03 | Green | Water / NDWI |

### 4.2 Spectral Change Detection

Bi-temporal analysis is performed between a baseline period (2019) and a monitoring period (2023). Four spectral indices are computed and differenced:

| Index | Name | Primary Signal |
|-------|------|---------------|
| NDVI | Normalized Difference Vegetation Index | Vegetation cover loss |
| BSI | Bare Soil Index | Bare earth exposure — primary mining signal |
| NDWI | Normalized Difference Water Index | Water body disturbance |
| NBR | Normalized Burn Ratio | Soil and vegetation change proxy |

**Composite Mining Score** (validated weights):

```
mining_score = 0.35 × ΔNDVI + 0.30 × ΔBSI + 0.20 × ΔNDWI + 0.15 × ΔNBR
```

Any pixel with `mining_score ≥ 0.5` is classified as mining-altered.

### 4.3 False Positive Filtering

Prior to reporting, all detections are filtered against the OpenStreetMap Overpass API to exclude known residential, agricultural, and established industrial areas. This step is essential for urban-adjacent mining regions where legitimate land-cover change would otherwise generate spurious alerts.

### 4.4 Land Cover Classification

An unsupervised K-Means classifier is applied to the four-index feature space (NDVI, BSI, NDWI, NBR) to produce a four-class land cover map:

| Class | Indicator |
|-------|-----------|
| Forest | High NDVI |
| Mining-altered | High BSI |
| Water | High NDWI |
| Degraded / bare | Residual |

No labeled training data is required; the model is initialised from the spectral statistics of each scene and operates on any AOI without prior calibration.

### 4.5 U-Net Segmentation (Optional)

For deployments requiring higher spatial precision, a U-Net segmentation model is available:

- **Training data**: IIASA Global Land Cover dataset with mining-site annotations
- **Input**: 4-band Sentinel-2 tile (256 × 256 pixels)
- **Output**: Binary mining probability mask
- **Fallback**: Spectral Random Forest if model weights are unavailable

---

## 5. Verification Layer

Each detection that passes spectral thresholds is submitted to a three-tier legal verification chain.

### 5.1 Mining Lease Check

A PostGIS spatial query (or GeoJSON fallback) determines:
- Whether the detected location intersects any known mining lease polygon
- Whether the intersecting lease is **active** or **expired**

### 5.2 Environmental Clearance (EC) Check

Cross-referenced against MoEFCC and State Pollution Control Board records:
- Does the lease hold a valid environmental clearance?
- Is the clearance within its authorised date range?

### 5.3 Land Records Check

Cross-referenced against revenue and forest department records:
- Is the parcel classified as **forest land**?
- Is it **scheduled tribal land** under PESA 1996?
- Are additional statutory restrictions applicable?

### 5.4 Risk Scoring

```
base_score  = mining_score × 100
            + 40  (if outside all known lease boundaries)
            + 30  (if no valid environmental clearance)
            + 20  (if on forest or tribal land)

final_score = clamp(base_score, 0, 100)
```

**Alert thresholds:**

| Risk Level | Score Range | Action |
|------------|------------|--------|
| CRITICAL | ≥ 80 | Immediate WhatsApp alert to District Magistrate |
| HIGH | ≥ 60 | WhatsApp + SMS alert |
| MEDIUM | ≥ 40 | Logged; district office follow-up queue |
| LOW | < 40 | No action; record retained for audit |

---

## 6. Data Sources

| Source | Type | Resolution | Update Latency | Cost |
|--------|------|------------|----------------|------|
| Sentinel-2 L2A (Planetary Computer) | Optical raster | 10–60 m | 3–5 days | Free |
| Sentinel-1 GRD | SAR raster | 10 m | 1–3 days | Free |
| OSM Overpass API | Vector | — | Real-time | Free |
| Jharkhand Lease Registry | Vector polygon | — | Static (Gov API) | Gov API |
| MoEFCC EC Database | Tabular records | — | Static (web scrape) | Public |

---

## 7. Legal Framework

The verification layer and alert logic are implemented in accordance with the following statutes and instruments:

- **Mines and Minerals (Development and Regulation) Act, 1957** (amended 2021) — primary legislation governing mining leases and penalties for illegal extraction
- **Forest Conservation Act, 1980** — prohibits diversion of forest land without central government approval
- **Environment Protection Act, 1986** — basis for environmental clearance requirements
- **Panchayats (Extension to Scheduled Areas) Act, 1996 (PESA)** — statutory protections for tribal land and community rights in scheduled areas
- **National Green Tribunal Orders** — jurisdiction-specific orders on mining activity in Jharkhand

---

## 8. Scalability & Extensibility

The pipeline is AOI-agnostic by design. Extension to a new state or district requires no model retraining for spectral detection; spectral indices are physically grounded and universally applicable.

**To onboard a new AOI:**

1. Update `config/aoi.geojson` with the target bounding box.
2. Add lease boundary polygons to `config/lease_boundaries/`.
3. Update environmental clearance records in `config/ec_records.json`.
4. Run `scripts/seed_db.py` to initialise the verification database.

> **Note on U-Net portability**: The U-Net segmentation model may require fine-tuning for mining types that differ substantially from training data (e.g., open-cast quarrying vs. coal extraction vs. riverbed sand mining). Spectral K-Means remains the recommended baseline for new AOIs.

---

## 9. Demo Mode

A `--synthetic` flag enables a complete end-to-end demonstration without GPU resources or live satellite data access.

**Behaviour in demo mode:**

- Generates 8–12 synthetic `DetectionResult` objects distributed across the Jharkhand AOI
- Approximately **40%** of detections are placed outside lease boundaries, triggering CRITICAL or HIGH alerts
- Approximately **60%** are placed within active leases and are suppressed as legal
- The full verification and dispatch pipeline executes on synthetic data
- Total pipeline runtime: **< 10 seconds**

Demo mode is intended to validate pipeline logic, demonstrate the agentic loop to stakeholders, and facilitate development and testing in constrained environments.

---

## 10. References

- Ministry of Mines, Government of India. *MMDR Act 1957 (as amended, 2021).*
- Ministry of Environment, Forest and Climate Change (MoEFCC). *Environmental Clearance Guidelines.*
- European Space Agency. *Sentinel-2 User Handbook.*
- Microsoft Planetary Computer. *STAC API Documentation.* https://planetarycomputer.microsoft.com
- IIASA. *Global Land Use/Land Cover with Cropland Probability Dataset.*
- National Green Tribunal. *Orders pertaining to mining in Jharkhand (2019–2024).*

---

*For setup instructions, API reference, and contribution guidelines, see the [README](./README.md). For issue tracking and feature requests, use the [GitHub Issues](../../issues) page.*
