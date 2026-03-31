"""
src/dispatch/alerter.py — Alert dispatch via Twilio WhatsApp + SMS.
OWNER: Antigravity Agent 3

Dispatch chain (in order):
    1. Twilio WhatsApp  → if credentials present and alert qualifies
    2. Twilio SMS       → if WhatsApp fails
    3. Console log      → always fires as fallback (safe for demo)

Only detections with is_illegal == True are dispatched.
CRITICAL + HIGH → immediate dispatch
MEDIUM + LOW    → suppressed (logged only)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from src.utils.logger import logger
from src.utils.config import get_env, SETTINGS
from src.types import (
    AlertRecord,
    AlertStatus,
    RiskLevel,
    VerificationResult,
)


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

_RISK_EMOJI = {
    RiskLevel.CRITICAL: "🚨",
    RiskLevel.HIGH:     "⚠️",
    RiskLevel.MEDIUM:   "🟡",
    RiskLevel.LOW:      "🟢",
}


def build_alert_message(v: VerificationResult, area_ha: float, det_id: str) -> str:
    """Build the human-readable alert message sent to district magistrates."""
    emoji = _RISK_EMOJI.get(v.risk_level, "🔴")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"{emoji} ILLEGAL MINING ALERT — {v.risk_level.value}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Detection ID : {det_id}",
        f"Timestamp    : {timestamp}",
        f"Area Affected: {area_ha:.1f} hectares",
        f"Risk Score   : {v.risk_score:.0f}/100",
        f"Lease Status : {v.lease_status.value}",
    ]

    if v.lease_company:
        lines.append(f"Company (if any): {v.lease_company}")

    if v.ec_valid is False:
        lines.append("EC Status    : ❌ NO VALID ENVIRONMENTAL CLEARANCE")
    elif v.ec_valid is True:
        lines.append(f"EC Status    : ⚠️ Clearance {v.ec_id} — LEASE MAY BE EXPIRED")

    if v.land_type:
        lines.append(f"Land Type    : {v.land_type.upper()}")

    if v.notes:
        lines.append(f"Notes        : {'; '.join(v.notes)}")

    lines += [
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        "Action required: Initiate field inspection.",
        "Sent by: Autonomous Mining Detection System | MoEFCC",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Twilio dispatch (WhatsApp + SMS)
# ---------------------------------------------------------------------------

def _send_whatsapp(message: str) -> bool:
    """Attempt Twilio WhatsApp dispatch. Returns True on success."""
    account_sid = get_env("TWILIO_ACCOUNT_SID")
    auth_token  = get_env("TWILIO_AUTH_TOKEN")
    from_number = get_env("TWILIO_WHATSAPP_FROM")
    to_number   = get_env("TWILIO_WHATSAPP_TO")

    if not all([account_sid, auth_token, from_number, to_number]):
        logger.debug("Twilio WhatsApp creds not set — skipping.")
        return False

    try:
        from twilio.rest import Client  # type: ignore
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number,
        )
        logger.success("WhatsApp alert dispatched | SID: {}", msg.sid)
        return True
    except Exception as e:
        logger.warning("WhatsApp dispatch failed: {}", e)
        return False


def _send_sms(message: str) -> bool:
    """Attempt Twilio SMS dispatch. Returns True on success."""
    account_sid = get_env("TWILIO_ACCOUNT_SID")
    auth_token  = get_env("TWILIO_AUTH_TOKEN")
    from_number = get_env("TWILIO_SMS_FROM")
    to_number   = get_env("TWILIO_SMS_TO")

    if not all([account_sid, auth_token, from_number, to_number]):
        logger.debug("Twilio SMS creds not set — skipping.")
        return False

    try:
        from twilio.rest import Client  # type: ignore
        # SMS: truncate to 1600 chars (Twilio limit)
        sms_body = message[:1600]
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            body=sms_body,
            from_=from_number,
            to=to_number,
        )
        logger.success("SMS alert dispatched | SID: {}", msg.sid)
        return True
    except Exception as e:
        logger.warning("SMS dispatch failed: {}", e)
        return False


# ---------------------------------------------------------------------------
# Main dispatch function
# ---------------------------------------------------------------------------

def dispatch_alerts(
    verifications: list[VerificationResult],
    detections_map: dict[str, float] | None = None,
) -> list[AlertRecord]:
    """
    Dispatch alerts for all illegal detections.

    Parameters
    ----------
    verifications  : list[VerificationResult] from the verification layer
    detections_map : optional dict mapping detection_id → area_ha
                     (used to enrich the alert message with area info)

    Returns
    -------
    list[AlertRecord] — one per dispatched/suppressed alert
    """
    alerts: list[AlertRecord] = []
    cfg_alerts = SETTINGS.get("alerts", {})
    console_print = cfg_alerts.get("console_print", True)

    dispatch_levels = {RiskLevel.CRITICAL, RiskLevel.HIGH}

    for v in verifications:
        area_ha = (detections_map or {}).get(v.detection_id, 0.0)
        message  = build_alert_message(v, area_ha, v.detection_id)
        alert_id = f"ALERT-{uuid.uuid4().hex[:8].upper()}"

        # Suppress legal / low-risk activity
        if not v.is_illegal or v.risk_level not in dispatch_levels:
            logger.info(
                "Alert suppressed | {} | {} | score={:.0f}",
                v.detection_id, v.risk_level.value, v.risk_score
            )
            alerts.append(AlertRecord(
                alert_id=alert_id,
                detection_id=v.detection_id,
                risk_level=v.risk_level,
                lon=0.0, lat=0.0,
                area_ha=area_ha,
                lease_status=v.lease_status,
                risk_score=v.risk_score,
                message=message,
                whatsapp_status=AlertStatus.SUPPRESSED,
                sms_status=AlertStatus.SUPPRESSED,
            ))
            continue

        logger.info(
            "Dispatching alert | {} | {} | score={:.0f} | area={:.1f}ha",
            v.detection_id, v.risk_level.value, v.risk_score, area_ha
        )

        # Console print (always — safe for demo)
        if console_print:
            logger.warning("\n" + "=" * 56 + "\n" + message + "\n" + "=" * 56)

        # Attempt WhatsApp → SMS → fallback already handled above
        wa_status  = AlertStatus.PENDING
        sms_status = AlertStatus.PENDING

        if cfg_alerts.get("whatsapp_enabled", False):
            wa_ok = _send_whatsapp(message)
            wa_status = AlertStatus.DISPATCHED if wa_ok else AlertStatus.FAILED
        else:
            wa_status = AlertStatus.SUPPRESSED  # disabled in config

        if wa_status != AlertStatus.DISPATCHED:
            if cfg_alerts.get("sms_enabled", False):
                sms_ok = _send_sms(message)
                sms_status = AlertStatus.DISPATCHED if sms_ok else AlertStatus.FAILED
            else:
                sms_status = AlertStatus.SUPPRESSED

        record = AlertRecord(
            alert_id=alert_id,
            detection_id=v.detection_id,
            risk_level=v.risk_level,
            lon=0.0, lat=0.0,
            area_ha=area_ha,
            lease_status=v.lease_status,
            risk_score=v.risk_score,
            message=message,
            whatsapp_status=wa_status,
            sms_status=sms_status,
            dispatched_at=datetime.utcnow(),
        )
        alerts.append(record)

    dispatched = sum(1 for a in alerts if a.whatsapp_status == AlertStatus.DISPATCHED
                     or a.sms_status == AlertStatus.DISPATCHED)
    suppressed = sum(1 for a in alerts if a.whatsapp_status == AlertStatus.SUPPRESSED)
    logger.info(
        "Alert dispatch complete | total={} | dispatched={} | suppressed={}",
        len(alerts), dispatched, suppressed
    )
    return alerts


__all__ = ["dispatch_alerts", "build_alert_message"]
