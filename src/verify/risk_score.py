"""
src/verify/risk_score.py — Applies penalty score thresholds based on verification.

"""

from src.types import DetectionResult, LeaseStatus, RiskLevel
from src.utils.config import SETTINGS
from src.utils.logger import logger

def calculate_risk(
    det: DetectionResult,
    lease_status: LeaseStatus,
    ec_valid: bool | None,
    land_type: str | None
) -> tuple[float, RiskLevel, list[str]]:
    
    risk_cfg = SETTINGS.get("risk", {})
    thresholds = risk_cfg.get("thresholds", {"critical": 80, "high": 60, "medium": 40})
    
    # Base score (0-100 scale)
    base_score = det.mining_score * 100
    risk_score = base_score
    notes = []
    
    # Rule 1: Outside any known lease (Huge Penalty)
    if lease_status == LeaseStatus.OUTSIDE:
        penalty = risk_cfg.get("outside_lease_penalty", 40)
        risk_score += penalty
        notes.append(f"+{penalty} (Outside all known leases)")
    elif lease_status == LeaseStatus.INSIDE_EXPIRED:
        risk_score += 25
        notes.append("+25 (Lease is EXPIRED)")
        
    # Rule 2: Environmental Clearance violation
    if ec_valid is False:
        penalty = risk_cfg.get("no_ec_penalty", 30)
        risk_score += penalty
        notes.append(f"+{penalty} (No active EC found)")
        
    # Rule 3: Protected Land Area
    # E.g., tribal or forest areas.
    if land_type and land_type.lower() in ["forest", "tribal"]:
        risk_score += 20
        notes.append("+20 (Protected forest/tribal land)")
        
    # Clamp to max 100.0
    risk_score = min(risk_score, 100.0)
    
    # Evaluate Risk Band
    if risk_score >= thresholds.get("critical", 80):
        level = RiskLevel.CRITICAL
    elif risk_score >= thresholds.get("high", 60):
        level = RiskLevel.HIGH
    elif risk_score >= thresholds.get("medium", 40):
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW
        
    return risk_score, level, notes
