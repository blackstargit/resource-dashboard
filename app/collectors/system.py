"""
app/collectors/system.py
=========================
Host identity (name, OS, kernel, CPU model), boot time, uptime and battery.

In the container the host root is bind-mounted at DISK_PATH (/host), so the
real host identity is read from there rather than the container's own files.
"""
import platform
import socket
import time

from app.core.config import DISK_PATH
from app.core.logging import get_logger

logger = get_logger("collectors.system")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available — system monitoring disabled.")

# "" when native, else the host-root prefix (e.g. /host).
_BASE = "" if not DISK_PATH or DISK_PATH == "/" else DISK_PATH.rstrip("/")


def _read(path: str) -> str | None:
    try:
        with open(path) as fh:
            return fh.read().strip()
    except Exception:
        return None


def _hostname() -> str:
    raw = _read(f"{_BASE}/etc/hostname")
    if raw:
        for line in raw.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    return socket.gethostname()


def _os_name() -> str:
    # PRETTY_NAME from os-release, e.g. 'Ubuntu 22.04.4 LTS'.
    content = _read(f"{_BASE}/etc/os-release")
    if content:
        for line in content.splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    return platform.system()


def _cpu_model() -> str | None:
    content = _read(f"{_BASE}/proc/cpuinfo" if _BASE else "/proc/cpuinfo")
    if content:
        for line in content.splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or None


def get_system_stats() -> dict:
    """Return host identity, boot time, uptime and battery status."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    try:
        boot_time = psutil.boot_time()
        battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
        return {
            "hostname": _hostname(),
            "os": _os_name(),
            "kernel": platform.release(),  # shared host kernel
            "cpu_model": _cpu_model(),
            "boot_time": boot_time,
            "uptime_seconds": round(time.time() - boot_time),
            "battery_percent": round(battery.percent, 1) if battery else None,
            "battery_plugged": battery.power_plugged if battery else None,
        }
    except Exception as exc:
        logger.error("Error getting system stats: %s", exc)
        return {"error": str(exc)}
