"""FastAPI application factory for the Axon Web UI.

Creates a configured FastAPI app that wraps the StorageBackend,
serves API routes, and optionally mounts the frontend SPA.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def create_app(
    db_path: Path,
    repo_path: Path | None = None,
    watch: bool = False,
) -> FastAPI:
    """Build and return a fully configured FastAPI application.

    Args:
        db_path: Path to the KuzuDB database directory.
        repo_path: Root of the repository (for file serving and reindex).
        watch: When True, enables SSE event streaming and reindex support.

    Returns:
        A ready-to-run FastAPI instance.
    """
    from axon.core.storage.kuzu_backend import KuzuBackend

    storage = KuzuBackend()
    read_only = not watch
    storage.initialize(db_path, read_only=read_only)

    event_queue: asyncio.Queue | None = asyncio.Queue() if watch else None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        storage.close()
        logger.info("Storage backend closed")

    app = FastAPI(
        title="Axon Web UI",
        description="Graph-powered code intelligence engine",
        version="0.2.4",
        lifespan=lifespan,
    )

    app.state.storage = storage
    app.state.repo_path = repo_path
    app.state.event_queue = event_queue
    app.state.watch = watch

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://localhost(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    from axon.web.routes.analysis import router as analysis_router
    from axon.web.routes.cypher import router as cypher_router
    from axon.web.routes.diff import router as diff_router
    from axon.web.routes.events import router as events_router
    from axon.web.routes.files import router as files_router
    from axon.web.routes.graph import router as graph_router
    from axon.web.routes.processes import router as processes_router
    from axon.web.routes.search import router as search_router

    app.include_router(graph_router)
    app.include_router(search_router)
    app.include_router(analysis_router)
    app.include_router(files_router)
    app.include_router(cypher_router)
    app.include_router(diff_router)
    app.include_router(processes_router)
    app.include_router(events_router)

    # Mount frontend SPA if built assets exist
    frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app
