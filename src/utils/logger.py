"""
src/utils/logger.py — Centralized logging using loguru.
All modules import logger from here.
"""

import sys
import os
from pathlib import Path
from loguru import logger


def setup_logger(log_dir: str = "results/logs", level: str = "INFO") -> None:
    """Configure loguru for the full pipeline."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    logger.remove()  # Remove default handler

    # Console — clean, colored
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{module}</cyan>:<cyan>{line}</cyan> | {message}",
        colorize=True,
    )

    # File — full detail
    logger.add(
        os.path.join(log_dir, "pipeline_{time:YYYY-MM-DD}.log"),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {module}:{line} | {message}",
        rotation="1 day",
        retention="7 days",
        compression="zip",
    )

    logger.info("Logger initialized — level={}", level)


# Auto-setup on import using env var, default INFO
_level = os.getenv("LOG_LEVEL", "INFO").upper()
setup_logger(level=_level)

__all__ = ["logger", "setup_logger"]
