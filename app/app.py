"""
app/app.py
==========
FastAPI application factory.

Call create_app() to get a fully wired application instance.
This keeps application setup out of main.py so it is easy to
import in tests or other entry points without running the server.
"""
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core import auth
from app.core.config import API_V1_PREFIX, FRONTEND_DIST
from app.core.logging import get_logger, setup_logging
from app.routers import auth as auth_router
from app.routers import resources, stream

logger = get_logger("app")

# Everything else under /api/ must carry a valid request signature.
PUBLIC_PATHS = {
    f"{API_V1_PREFIX}/auth/challenge",
    f"{API_V1_PREFIX}/auth/login",
}


def create_app() -> FastAPI:
    """Construct and return the FastAPI application."""
    setup_logging()

    app = FastAPI(
        title="AI Resource Monitor",
        description=(
            "Unified system resource monitoring dashboard. "
            "Streams real-time CPU, RAM, Disk, and GPU statistics."
        ),
        version="1.1.0",
    )

    logger.info("Auth: %s", auth.seed_admin())

    # -- Auth gate ------------------------------------------------------------
    # One middleware instead of per-route dependencies: every current and
    # future /api/ route is covered by default, including the SSE stream and
    # the process-kill endpoint.
    #
    # Credentials are read from headers, falling back to query parameters,
    # because EventSource cannot set headers and the SSE stream needs signing
    # too. Nothing here is a bearer token: the signature is over this exact
    # method and path, is single-use, and expires within seconds.
    @app.middleware("http")
    async def require_signature(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in PUBLIC_PATHS:
            q = request.query_params
            h = request.headers
            ok = auth.verify_request(
                session_id=h.get("X-Auth-Session") or q.get("s"),
                method=request.method,
                path=path,
                ts=h.get("X-Auth-Timestamp") or q.get("t"),
                nonce=h.get("X-Auth-Nonce") or q.get("n"),
                sig=h.get("X-Auth-Signature") or q.get("g"),
            )
            if not ok:
                return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    # -- Routers --------------------------------------------------------------
    app.include_router(auth_router.router)
    app.include_router(resources.router)
    app.include_router(stream.router)

    # -- Frontend (SPA) -------------------------------------------------------
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
