"""FastAPI application entry point."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bibliomap import __version__
from bibliomap.api import imports, openalex, workspaces

app = FastAPI(title="Bibliomap API", version=__version__)

# The Vite dev server proxies /api, so CORS is only needed for other origins.
_origins = [o for o in os.environ.get("BIBLIOMAP_CORS_ORIGINS", "").split(",") if o]
if _origins:
    app.add_middleware(
        CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"]
    )

app.include_router(imports.router)
app.include_router(openalex.router)
app.include_router(workspaces.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
