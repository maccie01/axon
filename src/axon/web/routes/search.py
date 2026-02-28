"""Search API route — hybrid search across the knowledge graph."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])

_EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"


class SearchRequest(BaseModel):
    """Body for the POST /search endpoint."""

    query: str
    limit: int = Field(default=20, ge=1, le=200)


@router.post("/search")
def search(body: SearchRequest, request: Request) -> dict:
    """Run hybrid search (FTS + optional vector) and return results."""
    from axon.core.search.hybrid import hybrid_search

    storage = request.app.state.storage

    # Attempt to compute a query embedding; fall back to FTS-only on failure.
    query_embedding: list[float] | None = None
    try:
        from axon.core.embeddings.embedder import _get_model

        model = _get_model(_EMBED_MODEL_NAME)
        query_embedding = list(next(iter(model.embed([body.query]))))
    except Exception:
        logger.debug("Query embedding failed, falling back to FTS only", exc_info=True)

    try:
        results = hybrid_search(
            body.query,
            storage,
            query_embedding=query_embedding,
            limit=body.limit,
        )
    except Exception as exc:
        logger.error("Search failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed") from exc

    return {
        "results": [
            {
                "nodeId": r.node_id,
                "score": r.score,
                "name": r.node_name,
                "filePath": r.file_path,
                "label": r.label,
                "snippet": r.snippet,
            }
            for r in results
        ]
    }
