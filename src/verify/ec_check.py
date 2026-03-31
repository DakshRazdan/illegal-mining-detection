"""
src/verify/ec_check.py — Checks environmental clearances (EC).
OWNER: Gemini
"""

import json
from datetime import datetime
from pathlib import Path
from src.utils.logger import logger

_EC_PATH = Path("config/ec_records.json")
_EC_CACHE = {}

def load_ec_records():
    if not _EC_CACHE and _EC_PATH.exists():
        with open(_EC_PATH) as f:
            data = json.load(f)
            records = data.get("ec_records", [])
            for r in records:
                _EC_CACHE[r["lease_id"]] = r
        logger.debug(f"Loaded {len(_EC_CACHE)} EC records from {_EC_PATH.name}")

def check_ec(lease_id: str | None) -> tuple[bool | None, str | None]:
    """
    Returns (is_valid: bool, ec_id: str).
    Returns (None, None) if no matching EC record is found.
    """
    if not lease_id:
        return None, None
        
    load_ec_records()
    record = _EC_CACHE.get(lease_id)
    
    if not record:
        return None, None
        
    ec_id = record.get("ec_id")
    status = record.get("status")
    valid_until_str = record.get("valid_until")
    
    if status != "ACTIVE":
        return False, ec_id
        
    try:
        valid_until = datetime.strptime(valid_until_str, "%Y-%m-%d")
        if valid_until > datetime.utcnow():
            return True, ec_id
        else:
            return False, ec_id
    except Exception as e:
        logger.warning(f"Error parsing EC date for {lease_id}: {e}")
        return False, ec_id
