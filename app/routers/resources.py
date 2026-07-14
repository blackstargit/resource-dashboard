"""
app/routers/resources.py
========================
REST endpoints for system resource statistics.

All routes are prefixed at /api/v1/resources.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.core.config import API_V1_PREFIX
from app.collectors.cpu import get_cpu_stats, PSUTIL_AVAILABLE
from app.collectors.ram import get_ram_stats
from app.collectors.disk import get_disk_stats
from app.collectors.gpu import get_gpu_stats, NVML_AVAILABLE
from app.collectors.processes import get_process_stats, get_top_processes, kill_process
from app.collectors.system import get_system_stats

router = APIRouter(prefix=f"{API_V1_PREFIX}/resources")


@router.get("/stats")
async def get_all_stats():
    """Return a single snapshot of all system resource statistics."""
    return {
        "cpu": get_cpu_stats(),
        "ram": get_ram_stats(),
        "disk": get_disk_stats(),
        "gpus": get_gpu_stats(),
        "process": get_process_stats(),
        "system": get_system_stats(),
    }


@router.get("/health")
async def resource_health_check():
    """Report which monitoring capabilities are available on this host."""
    return {
        "status": "healthy",
        "capabilities": {
            "cpu_monitoring": PSUTIL_AVAILABLE,
            "ram_monitoring": PSUTIL_AVAILABLE,
            "disk_monitoring": PSUTIL_AVAILABLE,
            "gpu_monitoring": NVML_AVAILABLE,
        },
    }


@router.get("/processes")
async def get_process_list(limit: int = 25, sort_by: str = "cpu"):
    """Return the top N processes sorted by cpu, memory, or gpu_memory."""
    if sort_by not in ("cpu", "memory", "gpu_memory"):
        sort_by = "cpu"
    limit = max(1, min(100, limit))
    return JSONResponse(content=get_top_processes(limit=limit, sort_by=sort_by))


@router.delete("/processes/{pid}")
async def terminate_process(pid: int):
    """Terminate a process by PID (SIGTERM)."""
    try:
        kill_process(pid)
    except ProcessLookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"pid": pid, "terminated": True}
