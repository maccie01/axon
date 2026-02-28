"""Branch diff route — structural comparison between two git refs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from axon.web.routes.graph import _serialize_edge, _serialize_node

logger = logging.getLogger(__name__)

router = APIRouter(tags=["diff"])


class DiffRequest(BaseModel):
    """Body for the POST /diff endpoint."""

    base: str
    compare: str


@router.post("/diff")
def compute_diff(body: DiffRequest, request: Request) -> dict:
    """Compare two branches structurally and return added/removed/modified entities."""
    from axon.core.diff import diff_branches

    repo_path = request.app.state.repo_path
    if repo_path is None:
        raise HTTPException(status_code=400, detail="No repo_path configured")

    branch_range = f"{body.base}..{body.compare}"

    try:
        result = diff_branches(repo_path, branch_range)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Diff failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Diff operation failed") from exc

    return {
        "added": [_serialize_node(n) for n in result.added_nodes],
        "removed": [_serialize_node(n) for n in result.removed_nodes],
        "modified": [
            {"before": _serialize_node(base), "after": _serialize_node(current)}
            for base, current in result.modified_nodes
        ],
        "addedEdges": [_serialize_edge(r) for r in result.added_relationships],
        "removedEdges": [_serialize_edge(r) for r in result.removed_relationships],
    }
