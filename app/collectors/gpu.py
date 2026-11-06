"""
app/collectors/gpu.py
=====================
NVIDIA GPU statistics via pynvml, with a WMI fallback for
non-NVIDIA GPUs on Windows (Intel/AMD, no utilisation data).
"""
import json
import platform
from app.core.logging import get_logger

logger = get_logger("collectors.gpu")

# ── pynvml availability ───────────────────────────────────────────────────────
try:
    from pynvml import (
        nvmlInit,
        nvmlDeviceGetCount,
        nvmlDeviceGetHandleByIndex,
        nvmlDeviceGetMemoryInfo,
        nvmlDeviceGetUtilizationRates,
        nvmlDeviceGetTemperature,
        nvmlDeviceGetName,
        nvmlDeviceGetPowerUsage,
        nvmlDeviceGetEnforcedPowerLimit,
        nvmlDeviceGetClockInfo,
        nvmlDeviceGetFanSpeed,
        nvmlDeviceGetComputeRunningProcesses,
        nvmlDeviceGetGraphicsRunningProcesses,
        NVML_TEMPERATURE_GPU,
        NVML_CLOCK_SM,
        NVML_CLOCK_MEM,
        NVMLError,
    )
    NVML_AVAILABLE = True
    try:
        nvmlInit()
    except Exception as exc:
        logger.warning("Failed to initialise NVML: %s", exc)
        NVML_AVAILABLE = False
except ImportError:
    NVML_AVAILABLE = False
    logger.warning("pynvml not available — GPU monitoring disabled.")


# ── Public helpers ────────────────────────────────────────────────────────────

def get_gpu_stats() -> list:
    """
    Return a list of GPU stat dicts, one per device.

    NVIDIA GPUs are sourced from NVML (full data).
    On Windows, non-NVIDIA GPUs are added via a WMI query
    (name and VRAM only — no utilisation data available).
    """
    gpu_stats: list = []
    nvml_gpu_names: set = set()

    # 1. NVML — best data, NVIDIA only
    if NVML_AVAILABLE:
        try:
            for i in range(nvmlDeviceGetCount()):
                try:
                    handle = nvmlDeviceGetHandleByIndex(i)
                    info = nvmlDeviceGetMemoryInfo(handle)
                    util = nvmlDeviceGetUtilizationRates(handle)
                    temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
                    name = nvmlDeviceGetName(handle)

                    if isinstance(name, bytes):
                        name = name.decode("utf-8")
                    nvml_gpu_names.add(name)

                    # Optional per-device metrics: not every board/driver
                    # supports each, so a failure means "N/A", not an error.
                    def _opt(fn, *args):
                        try:
                            return fn(handle, *args)
                        except NVMLError:
                            return None

                    power = _opt(nvmlDeviceGetPowerUsage)          # milliwatts
                    limit = _opt(nvmlDeviceGetEnforcedPowerLimit)  # milliwatts
                    sm_clk = _opt(nvmlDeviceGetClockInfo, NVML_CLOCK_SM)
                    mem_clk = _opt(nvmlDeviceGetClockInfo, NVML_CLOCK_MEM)
                    fan = _opt(nvmlDeviceGetFanSpeed)

                    gpu_stats.append({
                        "gpu_id": i,
                        "name": name,
                        "load_percent": util.gpu,
                        "memory_used_gb": round(info.used / (1024**3), 2),
                        "memory_total_gb": round(info.total / (1024**3), 2),
                        "memory_percent": round((info.used / info.total) * 100, 2),
                        "temp_celsius": temp,
                        "power_w": round(power / 1000, 1) if power is not None else None,
                        "power_limit_w": round(limit / 1000) if limit is not None else None,
                        "clock_sm_mhz": sm_clk,
                        "clock_mem_mhz": mem_clk,
                        "fan_percent": fan,
                    })
                except NVMLError as exc:
                    logger.error("Error getting stats for GPU %d: %s", i, exc)
                    gpu_stats.append({"gpu_id": i, "error": str(exc)})
        except Exception as exc:
            logger.error("Error in NVML stats: %s", exc)
            if not gpu_stats:
                gpu_stats.append({"error": str(exc)})

    # 2. WMI fallback — Windows only, fills in Intel/AMD GPUs missed by NVML
    if platform.system() == "Windows":
        import subprocess
        try:
            cmd = (
                'powershell "Get-CimInstance Win32_VideoController '
                '| Select-Object Name, AdapterRAM | ConvertTo-Json"'
            )
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if result.returncode == 0 and result.stdout.strip():
                wmi_data = json.loads(result.stdout)
                if isinstance(wmi_data, dict):
                    wmi_data = [wmi_data]

                next_id = len(gpu_stats)
                for item in wmi_data:
                    name = item.get("Name", "Unknown GPU")
                    # Skip GPUs already captured by NVML
                    if any(name in nv or nv in name for nv in nvml_gpu_names):
                        continue
                    ram_bytes = item.get("AdapterRAM") or 0
                    gpu_stats.append({
                        "gpu_id": next_id,
                        "name": name,
                        "load_percent": 0,
                        "memory_used_gb": 0,
                        "memory_total_gb": round(ram_bytes / (1024**3), 2),
                        "memory_percent": 0,
                        "temp_celsius": 0,
                    })
                    next_id += 1
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Error getting Windows GPU stats: %s", exc)

    return gpu_stats


def get_gpu_process_info() -> dict:
    """
    Return {pid: {gpu_memory_mb, gpu_id}} for every GPU-using process.
    Returns an empty dict if NVML is unavailable.
    """
    if not NVML_AVAILABLE:
        return {}

    result: dict = {}
    try:
        for i in range(nvmlDeviceGetCount()):
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
                        mem_mb = round(p.usedGpuMemory / (1024**2), 1) if p.usedGpuMemory else 0.0
                        existing = result.get(p.pid)
                        if existing is None or mem_mb > existing["gpu_memory_mb"]:
                            result[p.pid] = {"gpu_memory_mb": mem_mb, "gpu_id": i}
            except NVMLError:
                continue
    except Exception as exc:
        logger.error("Error getting GPU process info: %s", exc)

    return result
