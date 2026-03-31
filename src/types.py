"""
src/types.py — Shared typed data structures for cross-module data flow.
All agents communicate through these types — never raw dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    CRITICAL = "CRITICAL"   # score >= 80
    HIGH     = "HIGH"       # score >= 60
    MEDIUM   = "MEDIUM"     # score >= 40
    LOW      = "LOW"        # score < 40


class LeaseStatus(str, Enum):
    INSIDE_ACTIVE   = "INSIDE_ACTIVE_LEASE"
    INSIDE_EXPIRED  = "INSIDE_EXPIRED_LEASE"
    OUTSIDE         = "OUTSIDE_ALL_LEASES"
    UNKNOWN         = "UNKNOWN"


class AlertStatus(str, Enum):
    PENDING    = "PENDING"
    DISPATCHED = "DISPATCHED"
    FAILED     = "FAILED"
    SUPPRESSED = "SUPPRESSED"   # legal activity, no alert needed


class DetectionMethod(str, Enum):
    SPECTRAL_RF  = "spectral_rf"   # K-Means + mining score
    UNET         = "unet"          # U-Net segmentation
    YOLO         = "yolo"          # YOLO object detection
    ENSEMBLE     = "ensemble"      # Fused result
    SYNTHETIC    = "synthetic"     # Demo mode — no real model


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass
class DetectionResult:
    """Output from detection layer. Consumed by verification layer."""
    detection_id:   str
    lon:            float
    lat:            float
    area_ha:        float
    mining_score:   float           # 0.0 – 1.0 (raw detection confidence)
    method:         DetectionMethod
    detected_at:    datetime        = field(default_factory=datetime.utcnow)
    bbox_pixels:    Optional[tuple] = None  # (row_min, col_min, row_max, col_max)
    extra:          dict            = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Output from verification layer. Consumed by dispatch layer."""
    detection_id:       str
    lease_status:       LeaseStatus
    lease_id:           Optional[str]
    lease_company:      Optional[str]
    ec_valid:           Optional[bool]
    ec_id:              Optional[str]
    land_type:          Optional[str]
    risk_score:         float           # 0 – 100
    risk_level:         RiskLevel
    is_illegal:         bool
    verified_at:        datetime        = field(default_factory=datetime.utcnow)
    notes:              list[str]       = field(default_factory=list)


@dataclass
class AlertRecord:
    """Dispatched alert record — saved to DB and returned to dashboard."""
    alert_id:           str
    detection_id:       str
    risk_level:         RiskLevel
    lon:                float
    lat:                float
    area_ha:            float
    lease_status:       LeaseStatus
    risk_score:         float
    message:            str
    whatsapp_status:    AlertStatus     = AlertStatus.PENDING
    sms_status:         AlertStatus     = AlertStatus.PENDING
    dispatched_at:      Optional[datetime] = None
    district:           Optional[str]   = None
    state:              str             = "Jharkhand"


@dataclass
class PipelineResult:
    """Full end-to-end pipeline output for one processing run."""
    run_id:             str
    aoi_name:           str
    detections:         list[DetectionResult]   = field(default_factory=list)
    verifications:      list[VerificationResult] = field(default_factory=list)
    alerts:             list[AlertRecord]        = field(default_factory=list)
    synthetic_mode:     bool                    = False
    started_at:         datetime                = field(default_factory=datetime.utcnow)
    completed_at:       Optional[datetime]      = None
    total_area_ha:      float                   = 0.0
    illegal_count:      int                     = 0
    legal_count:        int                     = 0


__all__ = [
    "RiskLevel",
    "LeaseStatus",
    "AlertStatus",
    "DetectionMethod",
    "DetectionResult",
    "VerificationResult",
    "AlertRecord",
    "PipelineResult",
]
