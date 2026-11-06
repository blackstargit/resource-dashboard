"""
app/collectors/cpu.py
=====================
CPU usage, frequency, load average and temperature via psutil.
"""
import os

from app.core.logging import get_logger

logger = get_logger("collectors.cpu")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available — CPU monitoring disabled.")


def _cpu_temp() -> float | None:
    """Best-effort CPU package temperature in °C, or None if unreadable.

    Inside a container this may be empty (hwmon not exposed) — callers treat
    None as "N/A" rather than an error.
    """
    if not hasattr(psutil, "sensors_temperatures"):
        return None
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None
    for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz", "zenpower"):
        entries = temps.get(key)
        if entries:
            pkg = next(
                (e for e in entries if "package" in (e.label or "").lower()),
                entries[0],
            )
            return round(pkg.current, 1)
    return None


def _load_avg() -> list[float] | None:
    """1/5/15-minute load average, or None where unsupported (Windows)."""
    try:
        return [round(x, 2) for x in os.getloadavg()]
    except (OSError, AttributeError):
        return None


def get_cpu_stats() -> dict:
    """Return CPU load %, per-core load, count, frequency, load avg and temp."""
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
            "load_avg": _load_avg(),
            "temp_celsius": _cpu_temp(),
        }
    except Exception as exc:
        logger.error("Error getting CPU stats: %s", exc)
        return {"error": str(exc)}
