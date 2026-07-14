"""
app/app.py
==========
FastAPI application factory.

Call create_app() to get a fully wired application instance.
This keeps application setup out of main.py so it is easy to
import in tests or other entry points without running the server.
"""
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import FRONTEND_DIST
from app.core.logging import get_logger, setup_logging
from app.routers import resources, stream

logger = get_logger("app")


def create_app() -> FastAPI:
    """Construct and return the FastAPI application."""
    setup_logging()

    app = FastAPI(
        title="Resource Monitor",
        description=(
            "Unified system resource monitoring dashboard. "
            "Streams real-time CPU, RAM, Disk, and GPU statistics."
        ),
        version="1.1.0",
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(resources.router)
    app.include_router(stream.router)

    # ── Frontend (SPA) ────────────────────────────────────────────────────────
    # The root route serves index.html explicitly so React handles its own routing.
    # StaticFiles is mounted AFTER all API routes so /api/v1/* is matched first.

    @app.get("/")
    async def serve_root():
        """Serve the React application entry point."""
        return FileResponse(FRONTEND_DIST / "index.html")

    if FRONTEND_DIST.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(FRONTEND_DIST), html=True),
            name="frontend",
        )
    else:
        logger.warning(
            "Frontend dist not found at %s. "
            "Run `npm run build` inside frontend/ first.",
            FRONTEND_DIST,
        )

    return app
