"""Analysis API routes — impact, dead code, coupling, communities, health, reindex."""

from __future__ import annotations

import logging
import threading
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query, Request

from axon.web.routes.graph import _serialize_node

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])


@router.get("/impact/{node_id:path}")
def get_impact(node_id: str, request: Request, depth: int = Query(default=3, ge=1, le=10)) -> dict:
    """Analyse the blast radius of a node by traversing callers up to *depth* hops."""
    storage = request.app.state.storage

    node = storage.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")

    affected_with_depth = storage.traverse_with_depth(node_id, depth, direction="callers")

    depths: dict[str, list[dict]] = defaultdict(list)
    for affected_node, hop in affected_with_depth:
        depths[str(hop)].append(_serialize_node(affected_node))

    return {
        "target": _serialize_node(node),
        "affected": len(affected_with_depth),
        "depths": dict(depths),
    }


@router.get("/dead-code")
def get_dead_code(request: Request) -> dict:
    """List all symbols flagged as dead code, grouped by file."""
    storage = request.app.state.storage

    try:
        rows = storage.execute_raw(
            "MATCH (n) WHERE n.is_dead = true "
            "RETURN n.id, n.name, n.file_path, n.start_line, labels(n) "
            "ORDER BY n.file_path"
        )
    except Exception as exc:
        logger.error("Dead code query failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Dead code query failed") from exc

    if not rows:
        return {"total": 0, "byFile": {}}

    by_file: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        name = row[1] if len(row) > 1 else "?"
        file_path = row[2] if len(row) > 2 else "?"
        start_line = row[3] if len(row) > 3 else 0
        node_type = row[4] if len(row) > 4 else "unknown"
        by_file[file_path].append({
            "name": name,
            "type": str(node_type),
            "line": start_line,
        })

    return {"total": len(rows), "byFile": dict(by_file)}


@router.get("/coupling")
def get_coupling(request: Request) -> dict:
    """Return temporal coupling pairs between files."""
    storage = request.app.state.storage

    try:
        rows = storage.execute_raw(
            "MATCH (a)-[r]->(b) WHERE r.rel_type = 'coupled_with' "
            "RETURN a.name, a.file_path, b.name, b.file_path, r.strength, r.co_changes"
        )
    except Exception as exc:
        logger.error("Coupling query failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Coupling query failed") from exc

    pairs = []
    for row in rows or []:
        pairs.append({
            "fileA": row[1] if len(row) > 1 else "",
            "fileB": row[3] if len(row) > 3 else "",
            "strength": row[4] if len(row) > 4 else 0.0,
            "coChanges": row[5] if len(row) > 5 else 0,
        })

    return {"pairs": pairs}


@router.get("/communities")
def get_communities(request: Request) -> dict:
    """Return community clusters with their member nodes."""
    storage = request.app.state.storage

    try:
        # Get community nodes
        community_rows = storage.execute_raw(
            "MATCH (c) WHERE labels(c) = 'Community' "
            "RETURN c.id, c.name"
        )
    except Exception as exc:
        logger.error("Communities query failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Communities query failed") from exc

    if not community_rows:
        return {"communities": []}

    communities = []
    for row in community_rows:
        cid = row[0] if row else ""
        cname = row[1] if len(row) > 1 else ""

        # Get members of this community
        try:
            member_rows = storage.execute_raw(
                f"MATCH (n)-[r]->(c) WHERE c.id = '{cid}' "
                f"AND r.rel_type = 'member_of' "
                f"RETURN n.id"
            )
        except Exception:
            member_rows = []

        member_ids = [r[0] for r in (member_rows or []) if r]

        # Get cohesion from community properties if available
        try:
            cohesion_rows = storage.execute_raw(
                f"MATCH (c) WHERE c.id = '{cid}' RETURN c.cohesion"
            )
            cohesion = (
                cohesion_rows[0][0]
                if cohesion_rows and cohesion_rows[0] and cohesion_rows[0][0] is not None
                else None
            )
        except Exception:
            cohesion = None

        communities.append({
            "id": cid,
            "name": cname,
            "memberCount": len(member_ids),
            "cohesion": cohesion,
            "members": member_ids,
        })

    return {"communities": communities}


@router.get("/health")
def get_health(request: Request) -> dict:
    """Compute a composite codebase health score from multiple dimensions."""
    storage = request.app.state.storage

    breakdown: dict[str, float] = {}

    # Dead code score (25%): 100 - (dead / total * 100)
    try:
        total_rows = storage.execute_raw("MATCH (n) WHERE n.start_line > 0 RETURN count(n)")
        dead_rows = storage.execute_raw("MATCH (n) WHERE n.is_dead = true RETURN count(n)")
        total_symbols = total_rows[0][0] if total_rows and total_rows[0] else 1
        dead_count = dead_rows[0][0] if dead_rows and dead_rows[0] else 0
        breakdown["deadCode"] = round(max(0.0, 100.0 - (dead_count / max(total_symbols, 1) * 100)), 1)
    except Exception:
        breakdown["deadCode"] = 100.0

    # Coupling score (20%): 100 - (high_coupling / total_coupling * 200)
    try:
        coupling_rows = storage.execute_raw(
            "MATCH ()-[r]->() WHERE r.rel_type = 'coupled_with' "
            "RETURN r.strength"
        )
        if coupling_rows:
            total_coupling = len(coupling_rows)
            high_coupling = sum(1 for row in coupling_rows if row[0] and row[0] > 0.7)
            breakdown["coupling"] = round(
                max(0.0, 100.0 - (high_coupling / max(total_coupling, 1) * 200)), 1
            )
        else:
            breakdown["coupling"] = 100.0
    except Exception:
        breakdown["coupling"] = 100.0

    # Modularity score (20%): community count as proxy
    try:
        comm_rows = storage.execute_raw(
            "MATCH (c) WHERE labels(c) = 'Community' RETURN count(c)"
        )
        comm_count = comm_rows[0][0] if comm_rows and comm_rows[0] else 0
        # Heuristic: 3-15 communities is ideal; fewer or too many is worse
        if comm_count == 0:
            breakdown["modularity"] = 20.0
        elif comm_count <= 15:
            breakdown["modularity"] = min(100.0, round(comm_count / 15.0 * 100, 1))
        else:
            # Diminishing returns above 15
            breakdown["modularity"] = round(max(50.0, 100.0 - (comm_count - 15) * 2), 1)
    except Exception:
        breakdown["modularity"] = 50.0

    # Confidence score (20%): avg(confidence) * 100 across CALLS edges
    try:
        conf_rows = storage.execute_raw(
            "MATCH ()-[r]->() WHERE r.rel_type = 'calls' RETURN avg(r.confidence)"
        )
        avg_conf = conf_rows[0][0] if conf_rows and conf_rows[0] and conf_rows[0][0] is not None else 0.8
        breakdown["confidence"] = round(min(100.0, avg_conf * 100), 1)
    except Exception:
        breakdown["confidence"] = 80.0

    # Coverage score (15%): symbols_in_processes / callable_symbols * 100
    try:
        callable_rows = storage.execute_raw(
            "MATCH (n) WHERE labels(n) IN ['Function', 'Method'] RETURN count(n)"
        )
        process_member_rows = storage.execute_raw(
            "MATCH (n)-[r]->() WHERE r.rel_type = 'step_in_process' RETURN count(DISTINCT n.id)"
        )
        callable_count = callable_rows[0][0] if callable_rows and callable_rows[0] else 1
        in_process = process_member_rows[0][0] if process_member_rows and process_member_rows[0] else 0
        breakdown["coverage"] = round(
            min(100.0, in_process / max(callable_count, 1) * 100), 1
        )
    except Exception:
        breakdown["coverage"] = 0.0

    # Weighted composite
    weights = {
        "deadCode": 0.25,
        "coupling": 0.20,
        "modularity": 0.20,
        "confidence": 0.20,
        "coverage": 0.15,
    }
    score = round(sum(breakdown[k] * weights[k] for k in weights), 1)

    return {"score": score, "breakdown": breakdown}


@router.post("/reindex")
def trigger_reindex(request: Request) -> dict:
    """Trigger a full reindex in a background thread.

    Only available when the app is started in watch mode (storage is read-write).
    """
    repo_path = request.app.state.repo_path
    if repo_path is None:
        raise HTTPException(status_code=400, detail="No repo_path configured")

    if not request.app.state.watch:
        raise HTTPException(status_code=400, detail="Reindex only available in watch mode")

    event_queue = request.app.state.event_queue

    def _run_reindex() -> None:
        from axon.core.ingestion.pipeline import run_pipeline
        from axon.core.storage.kuzu_backend import KuzuBackend

        if event_queue:
            try:
                event_queue.put_nowait({"type": "reindex_start", "data": {}})
            except Exception:
                pass

        try:
            storage = request.app.state.storage
            run_pipeline(repo_path, storage=storage, full=True)
            logger.info("Reindex completed for %s", repo_path)
        except Exception:
            logger.error("Reindex failed", exc_info=True)

        if event_queue:
            try:
                event_queue.put_nowait({"type": "reindex_complete", "data": {}})
            except Exception:
                pass

    thread = threading.Thread(target=_run_reindex, daemon=True)
    thread.start()

    return {"status": "started"}
