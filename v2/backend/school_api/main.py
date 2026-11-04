"""FastAPI application for the v2 «Школьник» platform.

Architecture
------------
* ``/api/v2`` — native FastAPI routers (JSON, Bearer tokens).
* ``/api/v1`` — the proven legacy JSON API, mounted through ASGI.  The Android
  app and existing integrations keep the exact same contract, but the data now
  lives in PostgreSQL.
* ``/`` — the React single-page application built with Vite.

The domain layer (``services/*``) is shared by both API generations, so a fix
in one place immediately applies everywhere.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from school_api.api import v2 as api_v2
from school_api.legacy.bootstrap import get_flask_app

ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST = ROOT / "v2" / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Importing the legacy app installs the PostgreSQL ``database`` module and
    # creates the schema when the database is empty.
    get_flask_app()
    yield


app = FastAPI(
    title="Школьник API",
    version="2.0.0",
    description="FastAPI gateway for the «Школьник» learning platform.",
    docs_url="/api/v2/docs",
    redoc_url=None,
    openapi_url="/api/v2/openapi.json",
    lifespan=lifespan,
)

# The Vite dev server runs on another origin.  Production is same-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v2.router, prefix="/api/v2")


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True, "service": "school-api", "version": "2.0.0"}


# --------------------------------------------------------------------------
#  Legacy API (Android and integrations).  Mounted after native routers so
#  ``/api/v2`` always wins.
# --------------------------------------------------------------------------
legacy_wsgi = get_flask_app()
from a2wsgi import WSGIMiddleware  # noqa: E402  (after legacy bootstrap)

_legacy_asgi = WSGIMiddleware(legacy_wsgi)


class LegacyApi:
    """ASGI shim that keeps the ``/api/v1`` prefix inside Flask's PATH_INFO.

    Starlette moves the mount prefix into ``root_path``; a2wsgi would then strip
    it from PATH_INFO, while the legacy app defines its routes with the prefix.
    Clearing ``root_path`` makes both generations agree on the URL.
    """

    async def __call__(self, scope, receive, send):
        if scope["type"] in {"http", "websocket"}:
            scope = dict(scope)
            scope["root_path"] = ""
        await _legacy_asgi(scope, receive, send)


app.mount("/api/v1", LegacyApi())


# The Android build and other root-level legacy endpoints live outside the
# ``/api/v1`` prefix (for example the APK at ``/download/android``).  They must
# keep working after the SPA takes over the domain.
app.mount("/download", LegacyApi())

# YouTube-обёртка (``/embed/youtube/<id>``) — обычная HTML-страница Flask.
# Android открывает её из WebView, поэтому корневой путь должен остаться
# доступным и после перехода на SPA.
app.mount("/embed", LegacyApi())


# --------------------------------------------------------------------------
#  React SPA
# --------------------------------------------------------------------------
if FRONTEND_DIST.is_dir():
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str, request: Request):
    """Serve the SPA shell for every non-API path (client-side routing)."""
    if full_path.startswith(("api/", "static/", "uploads/")):
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)

    candidate = (FRONTEND_DIST / full_path).resolve()
    if (
        full_path
        and FRONTEND_DIST in candidate.parents
        and candidate.is_file()
    ):
        return FileResponse(candidate)

    index = FRONTEND_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)

    return JSONResponse(
        {
            "ok": True,
            "service": "school-api",
            "hint": "Соберите фронтенд: cd v2/frontend && npm run build",
            "docs": "/api/v2/docs",
        }
    )


def run() -> None:
    """Console entry point: ``python -m school_api.main``."""
    import uvicorn

    uvicorn.run(
        "school_api.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("RELOAD", "").lower() in {"1", "true", "yes"},
    )


if __name__ == "__main__":
    run()
