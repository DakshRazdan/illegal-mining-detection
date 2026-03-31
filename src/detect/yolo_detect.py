"""
src/detect/yolo_detect.py — YOLOv11 bounding box inference.
OWNER: Gemini

Uses ultralytics. 
Gracefully falls back to empty result if weights are missing.
"""

from pathlib import Path
import numpy as np
from src.utils.logger import logger

_MODEL_PATH = Path("models/yolo/best.pt")
_MODEL = None

def _load_model():
    global _MODEL
    if not _MODEL_PATH.exists():
        return False
        
    try:
        from ultralytics import YOLO
        _MODEL = YOLO(_MODEL_PATH)
        return True
    except ImportError:
        logger.warning("ultralytics not installed. YOLO inference skipped.")
        return False
    except Exception as e:
        logger.error(f"Failed to load YOLO weights: {e}")
        return False

def run_yolo(stack: np.ndarray) -> list:
    """
    Run YOLO inference. 
    In actual use, we'd extract B04, B03, B02 to form an RGB image.
    Here we return an empty list if the model doesn't exist.
    """
    if _MODEL is None:
        if not _load_model():
            logger.info("YOLO weights not found at models/yolo/best.pt. Returning empty list.")
            return []
            
    try:
        # Pseudo-RGB reconstruction for standard YOLO image input:
        # Standard order in our 7-band stack: B04 (idx 0), B08 (1), B11 (2), B03 (3), B05 (4), B07 (5), B12 (6)
        # We don't have B02 (blue), so we simulate False-Color mapping (B08, B04, B03) -> (R, G, B)
        # This gives vegetation a red hue, bare soil a cyan/grey hue.
        b08 = stack[1, :, :]
        b04 = stack[0, :, :]
        b03 = stack[3, :, :]
        
        rgb = np.stack([b08, b04, b03], axis=-1)
        # Normalize to 0-255 uint8
        rgb = np.clip((rgb / 4000.0) * 255, 0, 255).astype(np.uint8)
        
        results = _MODEL(rgb, verbose=False)
        
        boxes = []
        for r in results:
            for box in r.boxes:
                # [x1, y1, x2, y2, conf, class]
                b = box.xyxy[0].tolist()
                conf = box.conf[0].item()
                if conf > 0.5:
                    boxes.append({
                        "bbox": b,
                        "confidence": conf
                    })
        return boxes
    except Exception as e:
        logger.error(f"YOLO inference failed: {e}")
        return []
