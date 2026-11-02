"""Server-written receipt for every finished agent task.

The agent never writes this file: the server builds it from its own records (the run row, the files it hashed after the
task, the task's events) and stores it outside the project workspace, so nothing an agent does inside the workspace can
alter or forge it. Experiment runs have their own receipts (exprun.py); this covers chat, paper stages, loops and tools.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import workspace
from .config import settings
from .db import Store

SCHEMA_VERSION = 1


def _dir(project_id: str) -> Path:
    return settings.data_dir / "receipts" / "agents" / project_id


def path_for(project_id: str, run_id: str) -> Path:
    return _dir(project_id) / f"{run_id}.json"


def _parent(kind: str) -> dict:
    """`paper:write` -> parent paper stage; `loop:idea_forge` -> parent loop type; anything else is a direct task."""
    head, _, tail = (kind or "").partition(":")
    if head == "paper":
        return {"type": "paper_stage", "id": tail or None}
    if head == "loop":
        return {"type": "loop", "id": tail or None}
    return {"type": "direct", "id": None}


def build(store: Store, run_id: str) -> dict | None:
    run = store.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not run:
        return None
    arts = store.all("SELECT path, sha256, size, change FROM artifacts WHERE run_id=? ORDER BY id", (run_id,))
    text = run.get("result_text") or ""
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "project_id": run["project_id"],
        "conversation_id": run["conversation_id"],
        "operation": run["kind"],
        "parent": _parent(run["kind"]),
        "agent": {"provider": run["provider"], "model": run.get("model")},
        "permitted_workspace": f"projects/{run['project_id']}/workspace",
        "status": run["status"],
        "error": (run.get("error") or "")[:500] or None,
        "created_at": run["created_at"], "started_at": run.get("started_at"), "finished_at": run.get("finished_at"),
        "duration_ms": run.get("duration_ms"), "cost_usd": run.get("cost_usd"),
        "prompt_sha256": hashlib.sha256((run.get("prompt") or "").encode("utf-8")).hexdigest(),
        "result_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
        "artifacts": [dict(a) for a in arts],
        "written_by": "server",
    }


def write(store: Store, run_id: str) -> Path | None:
    """Create the receipt once the run is final. Never overwrites an earlier receipt (a receipt is a record)."""
    rec = build(store, run_id)
    if not rec or rec["agent"]["provider"] == "server_exec":
        return None
    out = path_for(rec["project_id"], run_id)
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(rec, indent=2, sort_keys=True)
    rec_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    out.write_text(json.dumps({**rec, "receipt_sha256": rec_sha}, indent=2, sort_keys=True), encoding="utf-8")
    return out


def safe_write(store: Store, run_id: str) -> None:
    try:
        write(store, run_id)
    except Exception as exc:  # noqa: BLE001 — a receipt problem must never fail the task itself
        store.log_activity(None, "agent_receipt_failed", f"{run_id}: {str(exc)[:300]}")


def read(project_id: str, run_id: str) -> dict | None:
    p = path_for(project_id, run_id)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def verify(rec: dict) -> bool:
    """True when the stored receipt still matches its own hash (detects hand edits to the file)."""
    body = {k: v for k, v in rec.items() if k != "receipt_sha256"}
    return hashlib.sha256(json.dumps(body, indent=2, sort_keys=True).encode("utf-8")).hexdigest() == rec.get("receipt_sha256")


def listing(store: Store, project_id: str, limit: int = 100) -> list[dict]:
    out = []
    for r in store.all("SELECT id FROM runs WHERE project_id=? AND provider!='server_exec' AND status IN "
                       "('succeeded','failed','cancelled') ORDER BY created_at DESC LIMIT ?", (project_id, limit)):
        rec = read(project_id, r["id"])
        if rec:
            out.append({"run_id": r["id"], "operation": rec["operation"], "status": rec["status"],
                        "finished_at": rec["finished_at"], "artifacts": len(rec["artifacts"]), "intact": verify(rec)})
    return out
