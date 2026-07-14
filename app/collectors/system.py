"""
app/collectors/system.py
=========================
Boot time, uptime, and battery statistics via psutil.
"""
import time
from app.core.logging import get_logger

logger = get_logger("collectors.system")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available — system monitoring disabled.")


def get_system_stats() -> dict:
    """Return boot time, uptime, and battery status (None if no battery present)."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    try:
        boot_time = psutil.boot_time()
        battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
        return {
            "boot_time": boot_time,
            "uptime_seconds": round(time.time() - boot_time),
            "battery_percent": round(battery.percent, 1) if battery else None,
            "battery_plugged": battery.power_plugged if battery else None,
        }
    except Exception as exc:
        logger.error("Error getting system stats: %s", exc)
        return {"error": str(exc)}
