"""
app/collectors/disk.py
======================
Disk usage and I/O statistics via psutil.
"""
from app.core.logging import get_logger

logger = get_logger("collectors.disk")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available — disk monitoring disabled.")


def get_disk_stats() -> dict:
    """Return root partition usage and cumulative read/write counters in MB."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    try:
        disk = psutil.disk_usage("/")
        disk_io = psutil.disk_io_counters()
        return {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": round(disk.percent, 2),
            "read_mb": round(disk_io.read_bytes / (1024**2), 2) if disk_io else None,
            "write_mb": round(disk_io.write_bytes / (1024**2), 2) if disk_io else None,
        }
    except Exception as exc:
        logger.error("Error getting disk stats: %s", exc)
        return {"error": str(exc)}
