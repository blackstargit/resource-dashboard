"""
app/collectors/cpu.py
=====================
CPU usage and frequency statistics via psutil.
"""
from app.core.logging import get_logger

logger = get_logger("collectors.cpu")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available — CPU monitoring disabled.")


def get_cpu_stats() -> dict:
    """Return CPU load percentage, core count, and current/max frequency."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    try:
        per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        cpu_freq = psutil.cpu_freq()
        return {
            "percent": round(sum(per_core) / len(per_core), 2) if per_core else 0.0,
            "per_core_percent": [round(p, 2) for p in per_core],
            "count": psutil.cpu_count(),
            "freq_mhz": round(cpu_freq.current, 2) if cpu_freq else None,
            "freq_max_mhz": round(cpu_freq.max, 2) if cpu_freq else None,
        }
    except Exception as exc:
        logger.error("Error getting CPU stats: %s", exc)
        return {"error": str(exc)}
