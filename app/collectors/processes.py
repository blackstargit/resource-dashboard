"""
app/collectors/processes.py
===========================
System process list and backend-process self-monitoring.

The module-level _process_cache retains psutil.Process objects between
requests so that cpu_percent() has a meaningful prior-interval baseline
(first call always returns 0.0 — subsequent calls return real deltas).
"""
import os
import time
from typing import Any, Dict

from app.core.logging import get_logger
from app.collectors.gpu import NVML_AVAILABLE, get_gpu_process_info

logger = get_logger("collectors.processes")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available — process monitoring disabled.")

# Retained between requests to give cpu_percent() a valid baseline
_process_cache: Dict[int, Any] = {}


def get_process_stats() -> dict:
    """Return CPU and memory stats for the current (backend) process."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    try:
        proc = psutil.Process()
        return {
            "cpu_percent": round(proc.cpu_percent(interval=0.1), 2),
            "memory_mb": round(proc.memory_info().rss / (1024**2), 2),
            "memory_percent": round(proc.memory_percent(), 2),
            "num_threads": proc.num_threads(),
            "num_fds": proc.num_fds() if hasattr(proc, "num_fds") else None,
        }
    except Exception as exc:
        logger.error("Error getting process stats: %s", exc)
        return {"error": str(exc)}


def get_top_processes(limit: int = 25, sort_by: str = "cpu") -> Dict[str, Any]:
    """
    Return the top N processes sorted by cpu, memory, or gpu_memory.

    GPU memory is cross-referenced from NVML via get_gpu_process_info().
    Zombie processes are skipped. Dead PIDs are evicted from the cache.
    """
    if not PSUTIL_AVAILABLE:
        return {
            "processes": [],
            "total_shown": 0,
            "sort_by": sort_by,
            "gpu_available": NVML_AVAILABLE,
            "timestamp": 0.0,
        }

    gpu_map = get_gpu_process_info()
    cpu_count = psutil.cpu_count() or 1
    processes: list = []
    seen_pids: set = set()

    try:
        for proc in psutil.process_iter():
            try:
                pid = proc.pid
                seen_pids.add(pid)

                # Reuse cached Process object for a valid cpu_percent baseline
                if pid not in _process_cache:
                    _process_cache[pid] = proc
                cached = _process_cache[pid]

                if cached.status() == psutil.STATUS_ZOMBIE:
                    continue

                raw_cpu = cached.cpu_percent(interval=None)
                mem_info = cached.memory_info()
                gpu_info = gpu_map.get(pid)

                processes.append({
                    "pid": pid,
                    "name": cached.name(),
                    "cpu_percent": round(raw_cpu / cpu_count, 2),
                    "memory_mb": round(mem_info.rss / (1024**2), 2),
                    "memory_percent": round(cached.memory_percent(), 2),
                    "gpu_memory_mb": gpu_info["gpu_memory_mb"] if gpu_info else None,
                    "gpu_id": gpu_info["gpu_id"] if gpu_info else None,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as exc:
        logger.error("Error iterating processes: %s", exc)

    # Evict dead PIDs from cache
    for pid in set(_process_cache) - seen_pids:
        _process_cache.pop(pid, None)

    sort_key = {
        "cpu": lambda p: p["cpu_percent"],
        "memory": lambda p: p["memory_mb"],
        "gpu_memory": lambda p: p["gpu_memory_mb"] or 0.0,
    }.get(sort_by, lambda p: p["cpu_percent"])

    processes.sort(key=sort_key, reverse=True)

    return {
        "processes": processes[:limit],
        "total_shown": min(len(processes), limit),
        "sort_by": sort_by,
        "gpu_available": NVML_AVAILABLE,
        "timestamp": time.time(),
    }


def kill_process(pid: int) -> None:
    """
    Terminate a process by PID (SIGTERM).

    Raises ProcessLookupError if the PID doesn't exist, PermissionError if
    denied or if the PID is this backend's own process.
    """
    if not PSUTIL_AVAILABLE:
        raise RuntimeError("psutil not available")
    if pid == os.getpid():
        raise PermissionError("Refusing to terminate the monitoring backend itself.")

    try:
        psutil.Process(pid).terminate()
    except psutil.NoSuchProcess:
        raise ProcessLookupError(f"No process with pid {pid}")
    except psutil.AccessDenied:
        raise PermissionError(f"Access denied to terminate pid {pid}")
