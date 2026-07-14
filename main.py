"""
Resource Monitoring
===================
Unified backend + frontend for system resource monitoring (GPU, CPU, RAM, Disk).
FastAPI serves the React frontend from frontend/dist and provides real-time
streaming stats via SSE.
"""

import asyncio
import logging
import json
import platform
import os
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

# Configuration
PORT = int(os.getenv("PORT", 8202))
HOST = os.getenv("HOST", "127.0.0.1")
API_V1_PREFIX = "/api/v1"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("resource-monitoring")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available, CPU/RAM monitoring will be disabled")

try:
    from pynvml import (
        nvmlInit,
        nvmlDeviceGetCount,
        nvmlDeviceGetHandleByIndex,
        nvmlDeviceGetMemoryInfo,
        nvmlDeviceGetUtilizationRates,
        nvmlDeviceGetTemperature,
        nvmlDeviceGetName,
        nvmlDeviceGetComputeRunningProcesses,
        nvmlDeviceGetGraphicsRunningProcesses,
        NVML_TEMPERATURE_GPU,
        NVMLError,
    )

    NVML_AVAILABLE = True
    try:
        nvmlInit()
    except Exception as e:
        logging.warning(f"Failed to initialize NVML: {e}")
        NVML_AVAILABLE = False
except ImportError:
    NVML_AVAILABLE = False
    logger.warning("pynvml (nvidia-ml-py) not available, GPU monitoring will be disabled")

# FastAPI App
app = FastAPI(
    title="Resource Monitoring API",
    description="Isolated API for system resource monitoring",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statistics Helpers (Copied from resources.py)

def get_cpu_stats() -> dict:
    """Get CPU statistics."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        return {
            "percent": round(cpu_percent, 2),
            "count": cpu_count,
            "freq_mhz": round(cpu_freq.current, 2) if cpu_freq else None,
            "freq_max_mhz": round(cpu_freq.max, 2) if cpu_freq else None,
        }
    except Exception as e:
        logger.error(f"Error getting CPU stats: {e}")
        return {"error": str(e)}


def get_ram_stats() -> dict:
    """Get RAM statistics."""
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
    except Exception as e:
        logger.error(f"Error getting RAM stats: {e}")
        return {"error": str(e)}


def get_disk_stats() -> dict:
    """Get disk statistics."""
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
    except Exception as e:
        logger.error(f"Error getting disk stats: {e}")
        return {"error": str(e)}


def get_gpu_stats() -> list:
    """Get GPU statistics using pynvml."""
    gpu_stats = []
    nvml_gpu_names = set()

    # 1. Try NVML first (best data)
    if NVML_AVAILABLE:
        try:
            device_count = nvmlDeviceGetCount()
            for i in range(device_count):
                try:
                    handle = nvmlDeviceGetHandleByIndex(i)
                    info = nvmlDeviceGetMemoryInfo(handle)
                    util = nvmlDeviceGetUtilizationRates(handle)
                    temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                    name = nvmlDeviceGetName(handle)

                    if isinstance(name, bytes):
                        name = name.decode("utf-8")

                    nvml_gpu_names.add(name)

                    gpu_stats.append(
                        {
                            "gpu_id": i,
                            "name": name,
                            "load_percent": util.gpu,
                            "memory_used_gb": round(info.used / (1024**3), 2),
                            "memory_total_gb": round(info.total / (1024**3), 2),
                            "memory_percent": round((info.used / info.total) * 100, 2),
                            "temp_celsius": temp,
                        }
                    )
                except NVMLError as e:
                    logger.error(f"Error getting stats for GPU {i}: {e}")
                    gpu_stats.append({"gpu_id": i, "error": str(e)})
        except Exception as e:
            logger.error(f"Error in NVML stats: {e}")
            if not gpu_stats:
                gpu_stats.append({"error": str(e)})

    # 2. On Windows, check for missed GPUs (Intel/AMD) via WMI
    if platform.system() == "Windows":
        try:
            import subprocess

            cmd = 'powershell "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json"'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

            if result.returncode == 0 and result.stdout.strip():
                try:
                    wmi_data = json.loads(result.stdout)
                    if isinstance(wmi_data, dict):
                        wmi_data = [wmi_data]

                    next_id = len(gpu_stats)

                    for item in wmi_data:
                        name = item.get("Name", "Unknown GPU")

                        if any(name in nv for nv in nvml_gpu_names) or any(
                            nv in name for nv in nvml_gpu_names
                        ):
                            continue

                        ram_bytes = item.get("AdapterRAM", 0) or 0
                        total_gb = round(ram_bytes / (1024**3), 2)

                        gpu_stats.append(
                            {
                                "gpu_id": next_id,
                                "name": name,
                                "load_percent": 0,
                                "memory_used_gb": 0,
                                "memory_total_gb": total_gb,
                                "memory_percent": 0,
                                "temp_celsius": 0,
                            }
                        )
                        next_id += 1
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.error(f"Error getting Windows GPU stats: {e}")

    return gpu_stats


def get_process_stats() -> dict:
    """Get current process statistics."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    try:
        process = psutil.Process()

        return {
            "cpu_percent": round(process.cpu_percent(interval=0.1), 2),
            "memory_mb": round(process.memory_info().rss / (1024**2), 2),
            "memory_percent": round(process.memory_percent(), 2),
            "num_threads": process.num_threads(),
            "num_fds": process.num_fds() if hasattr(process, "num_fds") else None,
        }
    except Exception as e:
        logger.error(f"Error getting process stats: {e}")
        return {"error": str(e)}

# Per-call CPU% baseline cache — retains Process objects between requests
_process_cache: Dict[int, Any] = {}


def get_gpu_process_info() -> Dict[int, Dict[str, Any]]:
    """Return {pid: {gpu_memory_mb, gpu_id}} for all GPU-using processes."""
    if not NVML_AVAILABLE:
        return {}

    result: Dict[int, Dict[str, Any]] = {}
    try:
        device_count = nvmlDeviceGetCount()
        for i in range(device_count):
            try:
                handle = nvmlDeviceGetHandleByIndex(i)
                for proc_list_fn in (
                    nvmlDeviceGetComputeRunningProcesses,
                    nvmlDeviceGetGraphicsRunningProcesses,
                ):
                    try:
                        procs = proc_list_fn(handle)
                    except NVMLError:
                        continue
                    for p in procs:
                        mem_mb = round(p.usedGpuMemory / (1024 ** 2), 1) if p.usedGpuMemory else 0.0
                        existing = result.get(p.pid)
                        if existing is None or mem_mb > existing["gpu_memory_mb"]:
                            result[p.pid] = {"gpu_memory_mb": mem_mb, "gpu_id": i}
            except NVMLError:
                continue
    except Exception as e:
        logger.error(f"Error getting GPU process info: {e}")

    return result


def get_top_processes(limit: int = 25, sort_by: str = "cpu") -> Dict[str, Any]:
    """Return top N processes sorted by cpu, memory, or gpu_memory."""
    if not PSUTIL_AVAILABLE:
        return {"processes": [], "total_shown": 0, "sort_by": sort_by, "gpu_available": NVML_AVAILABLE, "timestamp": 0.0}

    import time

    gpu_map = get_gpu_process_info()
    cpu_count = psutil.cpu_count() or 1
    processes = []
    seen_pids: set = set()

    try:
        for proc in psutil.process_iter():
            try:
                pid = proc.pid
                seen_pids.add(pid)

                # Reuse cached Process object so cpu_percent() has a prior baseline
                if pid not in _process_cache:
                    _process_cache[pid] = proc
                cached = _process_cache[pid]

                # First call plants baseline; subsequent calls return real delta
                raw_cpu = cached.cpu_percent(interval=None)
                normalized_cpu = round(raw_cpu / cpu_count, 2)

                mem_info = cached.memory_info()
                mem_mb = round(mem_info.rss / (1024 ** 2), 2)
                mem_pct = round(cached.memory_percent(), 2)
                name = cached.name()

                status = cached.status()
                if status == psutil.STATUS_ZOMBIE:
                    continue

                gpu_info = gpu_map.get(pid)
                processes.append({
                    "pid": pid,
                    "name": name,
                    "cpu_percent": normalized_cpu,
                    "memory_mb": mem_mb,
                    "memory_percent": mem_pct,
                    "gpu_memory_mb": gpu_info["gpu_memory_mb"] if gpu_info else None,
                    "gpu_id": gpu_info["gpu_id"] if gpu_info else None,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.error(f"Error iterating processes: {e}")

    # Clean up dead PIDs from cache
    dead_pids = set(_process_cache.keys()) - seen_pids
    for pid in dead_pids:
        _process_cache.pop(pid, None)

    sort_key = {
        "cpu": lambda p: p["cpu_percent"],
        "memory": lambda p: p["memory_mb"],
        "gpu_memory": lambda p: p["gpu_memory_mb"] or 0.0,
    }.get(sort_by, lambda p: p["cpu_percent"])

    processes.sort(key=sort_key, reverse=True)
    processes = processes[:limit]

    return {
        "processes": processes,
        "total_shown": len(processes),
        "sort_by": sort_by,
        "gpu_available": NVML_AVAILABLE,
        "timestamp": time.time(),
    }


# Routes

# Resolve the frontend dist directory relative to this file
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")

@app.get("/")
async def serve_root():
    """Serve the React app entry point."""
    return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))

@app.get(f"{API_V1_PREFIX}/resources/stats")
async def get_system_stats():
    """Get comprehensive system resource statistics."""
    return {
        "cpu": get_cpu_stats(),
        "ram": get_ram_stats(),
        "disk": get_disk_stats(),
        "gpus": get_gpu_stats(),
        "process": get_process_stats(),
    }

@app.get(f"{API_V1_PREFIX}/resources/stats/stream")
async def stream_system_stats(interval: Optional[float] = 1.0):
    """Stream system resource statistics in real-time."""
    interval = max(0.1, min(10.0, interval))

    async def generate_stats():
        try:
            while True:
                stats = {
                    "cpu": get_cpu_stats(),
                    "ram": get_ram_stats(),
                    "disk": get_disk_stats(),
                    "gpus": get_gpu_stats(),
                    "process": get_process_stats(),
                    "timestamp": asyncio.get_event_loop().time(),
                }
                yield f"data: {json.dumps(stats)}\n\n"
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("Stats streaming cancelled")
        except Exception as e:
            logger.error(f"Error in stats streaming: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stats(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.get(f"{API_V1_PREFIX}/resources/health")
async def resource_health_check():
    """Health check for resource monitoring."""
    return {
        "status": "healthy",
        "capabilities": {
            "cpu_monitoring": PSUTIL_AVAILABLE,
            "ram_monitoring": PSUTIL_AVAILABLE,
            "disk_monitoring": PSUTIL_AVAILABLE,
            "gpu_monitoring": NVML_AVAILABLE,
        },
    }

@app.get(f"{API_V1_PREFIX}/resources/processes")
async def get_process_list(limit: int = 25, sort_by: str = "cpu"):
    """Get top N processes sorted by CPU, memory, or GPU memory usage."""
    if sort_by not in ("cpu", "memory", "gpu_memory"):
        sort_by = "cpu"
    limit = max(1, min(100, limit))
    return JSONResponse(content=get_top_processes(limit=limit, sort_by=sort_by))


# Mount static assets (JS/CSS/images built by Vite)
# Must come AFTER all API routes so /api/v1/* is matched first
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
else:
    logger.warning(
        f"Frontend dist not found at {_FRONTEND_DIST}. "
        "Run `npm run build` inside the frontend/ directory first."
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
