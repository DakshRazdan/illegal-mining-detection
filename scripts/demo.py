"""
scripts/demo.py — End-to-end demo runner.
OWNER: Antigravity Agent 1

Usage:
    python scripts/demo.py --synthetic        # No GPU/model needed (demo mode)
    python scripts/demo.py                    # Real pipeline (requires model weights)

--synthetic generates 8-12 fake DetectionResult objects across the Jharkhand AOI,
some inside lease boundaries (legal), some outside (illegal). The full verification
and dispatch pipeline runs on the synthetic data — proving the agentic loop works.
"""

import argparse
import json
import random
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.logger import logger
from src.utils.config import SETTINGS
from src.types import (
    DetectionResult,
    DetectionMethod,
    PipelineResult,
)


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

# Lease bounding boxes from config (hardcoded mirrors of jharkhand_sample.geojson)
_LEASE_BOXES = [
    (85.88, 23.72, 85.96, 23.78),  # LEASE-JH-001 ACTIVE
    (86.00, 23.58, 86.10, 23.65),  # LEASE-JH-002 ACTIVE
    (85.82, 23.69, 85.86, 23.72),  # LEASE-JH-003 EXPIRED
    (85.92, 23.51, 86.02, 23.60),  # LEASE-JH-004 ACTIVE
]

_AOI_BOUNDS = (85.8, 23.5, 86.2, 23.8)


def _random_point_in_box(box: tuple) -> tuple[float, float]:
    min_lon, min_lat, max_lon, max_lat = box
    return (
        round(random.uniform(min_lon, max_lon), 5),
        round(random.uniform(min_lat, max_lat), 5),
    )


def _random_point_in_aoi_outside_leases() -> tuple[float, float]:
    """Random point inside AOI but outside all lease boxes."""
    from shapely.geometry import Point
    from src.utils.geo_utils import bbox_to_polygon

    aoi_poly = bbox_to_polygon(*_AOI_BOUNDS)
    lease_polys = [bbox_to_polygon(*b) for b in _LEASE_BOXES]

    for _ in range(1000):
        lon = round(random.uniform(_AOI_BOUNDS[0], _AOI_BOUNDS[2]), 5)
        lat = round(random.uniform(_AOI_BOUNDS[1], _AOI_BOUNDS[3]), 5)
        pt = Point(lon, lat)
        if aoi_poly.contains(pt) and not any(lp.contains(pt) for lp in lease_polys):
            return lon, lat

    # fallback
    return (85.87, 23.66)


def generate_synthetic_detections(n: int = 10) -> list[DetectionResult]:
    """
    Generate n synthetic DetectionResult objects.
    Mix: ~40% outside leases (will be flagged illegal), ~60% inside leases.
    """
    logger.info("Generating {} synthetic detections...", n)
    detections = []
    outside_count = max(2, int(n * 0.4))

    for i in range(n):
        det_id = f"SYN-{uuid.uuid4().hex[:8].upper()}"

        if i < outside_count:
            lon, lat = _random_point_in_aoi_outside_leases()
            score = round(random.uniform(0.65, 0.95), 3)
        else:
            box = random.choice(_LEASE_BOXES)
            lon, lat = _random_point_in_box(box)
            score = round(random.uniform(0.52, 0.78), 3)

        area = round(random.uniform(0.5, 45.0), 1)

        det = DetectionResult(
            detection_id=det_id,
            lon=lon,
            lat=lat,
            area_ha=area,
            mining_score=score,
            method=DetectionMethod.SYNTHETIC,
            detected_at=datetime.utcnow(),
        )
        detections.append(det)
        logger.debug("  {} | lon={:.4f} lat={:.4f} | score={} | area={}ha",
                     det_id, lon, lat, score, area)

    logger.success("Generated {} synthetic detections.", len(detections))
    return detections


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def run_synthetic_pipeline() -> PipelineResult:
    """Run full pipeline on synthetic data (no model weights needed)."""
    run_id = f"RUN-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    logger.info("=== SYNTHETIC DEMO RUN: {} ===", run_id)

    result = PipelineResult(
        run_id=run_id,
        aoi_name="Jharkhand Coal Belt (Synthetic)",
        synthetic_mode=True,
        started_at=datetime.utcnow(),
    )

    # Step 1 — Generate detections
    detections = generate_synthetic_detections(n=random.randint(8, 12))
    result.detections = detections

    # Step 2 — Verification (will be wired to src/verify when Terminal 2 completes)
    logger.info("Step 2: Verification — loading lease boundaries from GeoJSON fallback...")
    try:
        from src.verify.verifier import verify_detections
        verifications = verify_detections(detections)
        result.verifications = verifications
    except ImportError:
        logger.warning("src/verify not yet implemented — skipping verification step.")
        logger.warning("Run Claude Code Terminal 2 to implement verification.")

    # Step 3 — Dispatch (will be wired to src/dispatch when Agent 3 completes)
    logger.info("Step 3: Dispatch — sending alerts for illegal activity...")
    try:
        from src.dispatch.alerter import dispatch_alerts
        alerts = dispatch_alerts(result.verifications)
        result.alerts = alerts
    except ImportError:
        logger.warning("src/dispatch not yet implemented — skipping dispatch step.")

    # Step 4 — Dashboard
    logger.info("Step 4: Dashboard generation...")
    try:
        from scripts.generate_dashboard import generate
        dashboard_path = generate(result)
        logger.success("Dashboard generated: {}", dashboard_path)
    except (ImportError, Exception) as e:
        logger.warning("Dashboard generation skipped: {}", e)

    result.completed_at = datetime.utcnow()
    elapsed = (result.completed_at - result.started_at).total_seconds()
    logger.success("=== DEMO RUN COMPLETE in {:.1f}s ===", elapsed)

    # Summary
    illegal = sum(1 for v in result.verifications if v.is_illegal) if result.verifications else "TBD"
    legal   = sum(1 for v in result.verifications if not v.is_illegal) if result.verifications else "TBD"
    logger.info("Summary | Detections: {} | Illegal: {} | Legal: {} | Alerts: {}",
                len(detections), illegal, legal, len(result.alerts))

    return result


def run_real_pipeline() -> PipelineResult:
    """Run full pipeline with real Sentinel-2 data and trained models."""
    logger.warning("Real pipeline not yet implemented.")
    logger.info("Use --synthetic flag for demo mode.")
    raise NotImplementedError("Real pipeline requires Claude Code Terminal 1 (ingest + detect)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Illegal Mining Detection — Demo Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/demo.py --synthetic        Full demo without GPU
  python scripts/demo.py                    Real pipeline (needs model weights)
        """,
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        default=False,
        help="Use synthetic data (no GPU or model weights needed)",
    )
    args = parser.parse_args()

    if args.synthetic:
        run_synthetic_pipeline()
    else:
        model_path = Path("models/unet/best.pth")
        if not model_path.exists():
            logger.warning("Model weights not found at {}. Switching to --synthetic mode.", model_path)
            run_synthetic_pipeline()
        else:
            run_real_pipeline()


if __name__ == "__main__":
    main()
