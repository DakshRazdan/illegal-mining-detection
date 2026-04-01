"""
src/verify/verifier.py — Orchestrates the full Verification Pipeline.

"""

from src.types import DetectionResult, VerificationResult, RiskLevel, LeaseStatus
from src.verify.lease_check import check_lease
from src.verify.ec_check import check_ec
from src.verify.risk_score import calculate_risk
from src.utils.logger import logger

def verify_detections(detections: list[DetectionResult]) -> list[VerificationResult]:
    logger.info(f"Starting Verification Layer for {len(detections)} detections...")
    results = []
    
    for det in detections:
        # 1. Lease spatial query
        lease_status, lease_id, company = check_lease(det.lon, det.lat)
        
        # 2. Environmental Clearance check
        ec_valid, ec_id = check_ec(lease_id)
        
        # 3. Land records (mocked for demo unless config available)
        land_type = "forest" if det.lat > 23.7 else "general"
        
        # 4. Final Risk score evaluation
        risk_score, risk_level, notes = calculate_risk(
            det, lease_status, ec_valid, land_type
        )
        
        # 5. Is it Illegal? 
        # By definition: CRITICAL or HIGH means it demands attention/is illegal
        is_illegal = risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]
        
        # Override: If it's fully legal, it's not an illegal mine, just a detected one.
        if lease_status == LeaseStatus.INSIDE_ACTIVE and ec_valid is True:
            is_illegal = False
            risk_level = RiskLevel.LOW
            notes.append("System Override: Fully legal & validated mine.")
            
        if is_illegal:
            logger.warning(
                f"[{det.detection_id}] Flagged ILLEGAL ({risk_level.value}). "
                f"Score: {risk_score:.1f}. Reason: {', '.join(notes)}"
            )

        res = VerificationResult(
            detection_id=det.detection_id,
            lease_status=lease_status,
            lease_id=lease_id,
            lease_company=company,
            ec_valid=ec_valid,
            ec_id=ec_id,
            land_type=land_type,
            risk_score=risk_score,
            risk_level=risk_level,
            is_illegal=is_illegal,
            notes=notes
        )
        results.append(res)
        
    illegal_count = sum(1 for r in results if r.is_illegal)
    logger.success(f"Verification complete: {illegal_count} illegal flags / {len(results)} total.")
    return results
