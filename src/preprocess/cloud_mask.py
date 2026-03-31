"""
src/preprocess/cloud_mask.py — Applies SCL Scene Classification masking.
OWNER: Gemini
"""

import numpy as np
from pathlib import Path
from src.utils.logger import logger

def apply_cloud_masking(array_path: Path) -> Path:
    logger.info(f"Applying cloud mask to {array_path}...")
    try:
        arr = np.load(array_path)
        # Assuming the last band in the array is SCL (if we downloaded 8 bands total)
        # In SCL: 3=Cloud shadows, 8=Cloud med, 9=Cloud high, 10=Cirrus, 11=Snow/Ice
        if arr.shape[0] < 8:
            logger.warning("SCL band missing from array or array is stub, skipping masking.")
            return array_path

        scl = arr[-1, :, :]
        # Create mask for valid pixels 
        # (valid: 4=Vegetation, 5=Bare Soils, 6=Water, 7=Unclassified)
        valid_mask = np.isin(scl, [4, 5, 6, 7])
        
        # Apply mask to all bands except SCL, setting invalid to NaN
        masked_bands = []
        for i in range(arr.shape[0] - 1): # Exclude SCL itself
            band = arr[i, :, :]
            band[~valid_mask] = np.nan
            masked_bands.append(band)

        # Re-stack without SCL
        cleaned_arr = np.stack(masked_bands, axis=0)
        
        out_path = array_path.parent / f"{array_path.stem}_masked.npy"
        np.save(out_path, cleaned_arr)
        logger.success(f"Cloud masking applied. Output shape: {cleaned_arr.shape}")
        return out_path

    except Exception as e:
        logger.error(f"Cloud masking failed on {array_path}: {e}")
        return array_path
