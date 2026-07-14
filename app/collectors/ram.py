"""
app/collectors/ram.py
=====================
RAM and swap memory statistics via psutil.
"""
from app.core.logging import get_logger

logger = get_logger("collectors.ram")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available — RAM monitoring disabled.")


def get_ram_stats() -> dict:
    """Return physical RAM and swap usage in GB and as a percentage."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    try:
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total_gb": round(ram.total / (1024**3), 2),
            "available_gb": round(ram.available / (1024**3), 2),
            "used_gb": round(ram.used / (1024**3), 2),
            "percent": round(ram.percent, 2),
            "swap_total_gb": round(swap.total / (1024**3), 2),
            "swap_used_gb": round(swap.used / (1024**3), 2),
            "swap_percent": round(swap.percent, 2),
        }
    except Exception as exc:
        logger.error("Error getting RAM stats: %s", exc)
        return {"error": str(exc)}
