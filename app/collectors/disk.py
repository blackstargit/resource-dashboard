"""
app/collectors/disk.py
======================
Disk usage and I/O statistics via psutil. In the container the host root is
bind-mounted at DISK_PATH (/host), so all-mounts reads the host's mount table.
"""
import os

from app.core.config import DISK_PATH
from app.core.logging import get_logger

logger = get_logger("collectors.disk")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available — disk monitoring disabled.")

# Real on-disk filesystems worth showing; pseudo/virtual mounts are skipped.
REAL_FS = {
    "ext2", "ext3", "ext4", "xfs", "btrfs", "zfs", "f2fs",
    "vfat", "exfat", "ntfs", "reiserfs", "jfs", "ufs", "fuseblk",
}

# "" when monitoring the native root, else the host-root prefix (e.g. /host).
_BASE = "" if not DISK_PATH or DISK_PATH == "/" else DISK_PATH.rstrip("/")


def get_disk_stats() -> dict:
    """Return root partition usage and cumulative read/write counters in MB."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    try:
        disk = psutil.disk_usage(DISK_PATH)
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


def _mount_lines() -> list[str]:
    """`device mount fstype` lines, from the host mount namespace when possible.

    `/proc/1/mounts` (reachable because the container runs pid: host) lists the
    host's real mounts without the container runtime's per-file bind-mounts
    (e.g. the NVIDIA libraries), which otherwise masquerade as separate disks.
    """
    for path in ("/proc/1/mounts", f"{_BASE}/proc/mounts" if _BASE else "/proc/mounts"):
        try:
            with open(path) as fh:
                lines = fh.read().splitlines()
            if lines:
                return lines
        except Exception:
            continue
    try:
        return [
            f"{p.device} {p.mountpoint} {p.fstype}"
            for p in psutil.disk_partitions(all=False)
        ]
    except Exception:
        return []


def get_all_disks() -> list:
    """Usage per physical filesystem (one entry per device), largest first."""
    if not PSUTIL_AVAILABLE:
        return []

    # One entry per device, keeping its shortest mountpoint (so "/" wins over a
    # file bind-mount like "/usr/bin/nvidia-smi" on the same device).
    primary: dict = {}
    for line in _mount_lines():
        parts = line.split()
        if len(parts) < 3:
            continue
        device, mount, fstype = parts[0], parts[1].replace("\\040", " "), parts[2]
        if fstype not in REAL_FS:
            continue
        cur = primary.get(device)
        if cur is None or len(mount) < len(cur[0]):
            primary[device] = (mount, fstype)

    disks: list = []
    for device, (mount, fstype) in primary.items():
        # Mount paths from the host namespace are host paths; stat them through
        # the /host prefix. A psutil-fallback path already carries that prefix.
        if _BASE and mount.startswith(_BASE):
            display, stat_path = mount[len(_BASE):] or "/", mount
        elif _BASE:
            display, stat_path = mount, _BASE + mount
        else:
            display, stat_path = mount, mount
        try:
            usage = psutil.disk_usage(stat_path or "/")
        except Exception:
            continue
        disks.append({
            "mount": display,
            "device": os.path.basename(device) or device,
            "fstype": fstype,
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent": round(usage.percent, 2),
        })

    disks.sort(key=lambda d: d["total_gb"], reverse=True)
    return disks[:8]
