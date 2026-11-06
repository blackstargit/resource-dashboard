"""
app/collectors/network.py
=========================
Aggregate network throughput via psutil. Rates are computed from the delta
between consecutive calls; with network_mode: host these are the host NICs.
"""
import time

from app.core.logging import get_logger

logger = get_logger("collectors.network")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available — network monitoring disabled.")

# ponytail: single module-level sample is fine for one stream; if several
# concurrent callers ever need independent rates, key this by caller.
_prev: dict = {"ts": None, "sent": 0, "recv": 0}


def get_network_stats() -> dict:
    """Return RX/TX rate (MB/s) and cumulative totals (GB)."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    try:
        io = psutil.net_io_counters()
        now = time.time()
        rx_rate = tx_rate = 0.0
        if _prev["ts"] is not None:
            dt = now - _prev["ts"]
            if dt > 0:
                # max(0, …) guards against counter resets/wraps going negative.
                rx_rate = max(0.0, (io.bytes_recv - _prev["recv"]) / dt)
                tx_rate = max(0.0, (io.bytes_sent - _prev["sent"]) / dt)
        _prev.update(ts=now, sent=io.bytes_sent, recv=io.bytes_recv)
        return {
            "rx_mb_s": round(rx_rate / (1024**2), 2),
            "tx_mb_s": round(tx_rate / (1024**2), 2),
            "rx_total_gb": round(io.bytes_recv / (1024**3), 2),
            "tx_total_gb": round(io.bytes_sent / (1024**3), 2),
        }
    except Exception as exc:
        logger.error("Error getting network stats: %s", exc)
        return {"error": str(exc)}
