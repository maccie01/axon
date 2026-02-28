"""Process routes — list discovered execution processes with their steps."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["processes"])


@router.get("/processes")
def get_processes(request: Request) -> dict:
    """Query all Process nodes and their ordered steps."""
    storage = request.app.state.storage

    try:
        process_rows = storage.execute_raw(
            "MATCH (p) WHERE labels(p) = 'Process' RETURN p.id, p.name"
        )
    except Exception as exc:
        logger.error("Processes query failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Processes query failed") from exc

    if not process_rows:
        return {"processes": []}

    processes = []
    for row in process_rows:
        pid = row[0] if row else ""
        pname = row[1] if len(row) > 1 else ""

        # Get steps for this process, ordered by step_number
        try:
            step_rows = storage.execute_raw(
                f"MATCH (n)-[r]->(p) WHERE p.id = '{pid}' "
                f"AND r.rel_type = 'step_in_process' "
                f"RETURN n.id, r.step_number "
                f"ORDER BY r.step_number"
            )
        except Exception:
            step_rows = []

        steps = []
        for step_row in step_rows or []:
            steps.append({
                "nodeId": step_row[0] if step_row else "",
                "stepNumber": step_row[1] if len(step_row) > 1 else 0,
            })

        # Infer kind from process properties if available
        kind = None
        try:
            kind_rows = storage.execute_raw(
                f"MATCH (p) WHERE p.id = '{pid}' RETURN p.kind"
            )
            if kind_rows and kind_rows[0] and kind_rows[0][0]:
                kind = kind_rows[0][0]
        except Exception:
            pass

        processes.append({
            "name": pname,
            "kind": kind,
            "stepCount": len(steps),
            "steps": steps,
        })

    return {"processes": processes}
