"""
src/detect/unet_detect.py — U-Net segmentation inference.
OWNER: Gemini

Uses segmentation-models-pytorch. 
Gracefully falls back to a zeros mask if the model weights map is missing.
"""

import os
from pathlib import Path
import numpy as np
import torch
import segmentation_models_pytorch as smp
from src.utils.logger import logger

_MODEL_PATH = Path("models/unet/best.pth")
_MODEL = None

def _load_model():
    global _MODEL
    if not _MODEL_PATH.exists():
        return False
        
    try:
        # Assuming our Unet was trained on 7 input channels
        _MODEL = smp.Unet(
            encoder_name="resnet34",        
            encoder_weights=None,     
            in_channels=7,                  
            classes=1,                      
        )
        _MODEL.load_state_dict(torch.load(_MODEL_PATH, map_location=torch.device('cpu')))
        _MODEL.eval()
        return True
    except Exception as e:
        logger.error(f"Failed to load U-Net weights: {e}")
        return False

def run_unet(stack: np.ndarray) -> np.ndarray:
    """
    Run UNet inference on a 7-band numpy stack (Bands, H, W).
    Returns a binary mask (H, W).
    """
    if stack.shape[0] != 7:
        logger.warning(f"U-Net expects 7 bands, got {stack.shape[0]}. Returning stub mask.")
        return np.zeros((stack.shape[1], stack.shape[2]), dtype=np.uint8)

    if _MODEL is None:
        if not _load_model():
            logger.info("U-Net weights not found at models/unet/best.pth. Returning stub mask.")
            return np.zeros((stack.shape[1], stack.shape[2]), dtype=np.uint8)
            
    try:
        # Normalize simple min/max for inference (stub logic depending on actual training protocol)
        tensor = torch.from_numpy(stack.astype(np.float32) / 10000.0).unsqueeze(0)
        
        with torch.no_grad():
            output = _MODEL(tensor)
            prob = torch.sigmoid(output).squeeze().numpy()
            
        mask = (prob > 0.5).astype(np.uint8)
        return mask
    except Exception as e:
        logger.error(f"U-Net inference failed: {e}")
        return np.zeros((stack.shape[1], stack.shape[2]), dtype=np.uint8)
