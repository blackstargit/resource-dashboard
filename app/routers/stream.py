"""
app/routers/stream.py
=====================
Server-Sent Events (SSE) endpoint for real-time resource stats.

All routes are prefixed at /api/v1/resources.
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.config import API_V1_PREFIX
from app.collectors.cpu import get_cpu_stats
from app.collectors.ram import get_ram_stats
from app.collectors.disk import get_disk_stats
from app.collectors.gpu import get_gpu_stats
from app.collectors.processes import get_process_stats
from app.collectors.system import get_system_stats
from app.core.logging import get_logger

logger = get_logger("routers.stream")

router = APIRouter(prefix=f"{API_V1_PREFIX}/resources")


@router.get("/stats/stream")
async def stream_system_stats(interval: Optional[float] = 1.0):
    """
    Stream system resource statistics as Server-Sent Events.

    Query params:
      interval  — poll interval in seconds (clamped to 0.1 – 10.0, default 1.0)
    """
    interval = max(0.1, min(10.0, interval or 1.0))

    async def generate():
        try:
            while True:
                payload = {
                    "cpu": get_cpu_stats(),
                    "ram": get_ram_stats(),
                    "disk": get_disk_stats(),
                    "gpus": get_gpu_stats(),
                    "process": get_process_stats(),
                    "system": get_system_stats(),
                    "timestamp": asyncio.get_event_loop().time(),
                }
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("SSE stream cancelled by client.")
        except Exception as exc:
            logger.error("Error in SSE stream: %s", exc)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
