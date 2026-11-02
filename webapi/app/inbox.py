"""Approvals inbox: everything across all projects that is waiting for one click from the user.

Human-in-the-loop in one place: paper stages to approve, Director plans to approve,
failed steps to retry, and what is running right now. Read-only; the actions reuse the
existing endpoints (approve stage, run stage with feedback, approve plan).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import director, loops, paper_studio
from .config import settings
from .db import Store, now


def _dismissed_file():
    return settings.data_dir / "inbox_dismissed.json"


def dismissed() -> dict:
    try:
        return json.loads(_dismissed_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def dismiss(key: str) -> None:
    """Hide one decision. Its key includes its state, so it comes back if anything about it changes."""
    d = dismissed()
    d[key] = now()
    _dismissed_file().parent.mkdir(parents=True, exist_ok=True)
    _dismissed_file().write_text(json.dumps(d, indent=2), encoding="utf-8")


def _key(item: dict) -> str:
    return ":".join(str(item.get(k) or "") for k in ("kind", "project_id", "stage_id", "loop_id", "loop_state",
                                                     "conversation_id", "run_id", "status", "stage", "memory_id"))


def _summary(store: Store, run_id: str | None) -> str | None:
    if not run_id:
        return None
    r = store.one("SELECT result_text FROM runs WHERE id=?", (run_id,))
    text = (r or {}).get("result_text") or ""
    return text.strip()[:900] or None


def build(store: Store) -> dict:
    approve, retry, running = [], [], []
    projects = store.all("SELECT id, title, updated_at FROM projects WHERE status='active' ORDER BY updated_at DESC")
    for p in projects:
        v = paper_studio.view(store, p["id"])
        if not v:
            continue
        stages = v["stages"]
        for i, s in enumerate(stages):
            base = {"project_id": p["id"], "project": p["title"], "paper": v["topic"] or p["title"],
                    "stage_id": s["id"], "stage": s["title"], "step": f"{i + 1}/{len(stages)}",
                    "outputs": [o["path"] for o in s["outputs_found"] if o["exists"]],
                    # Only name the next stage when approving really starts it (manual stages wait for a click).
                    "next": stages[i + 1]["title"] if i + 1 < len(stages)
                    and stages[i + 1]["id"] not in paper_studio.MANUAL_START else None,
                    "autopilot": v.get("autopilot", True)}
            if s["status"] == "needs_review":
                approve.append({**base, "kind": "paper_stage", "summary": _summary(store, s["run_id"])})
            elif s["status"] in {"failed", "incomplete"}:
                retry.append({**base, "kind": "paper_stage", "status": s["status"],
                              "error": s["error"] or "Some required files were not produced."})
            elif s["status"] == "running":
                running.append({**base, "kind": "paper_stage"})
            elif s["status"] == "ready" and s["id"] in paper_studio.MANUAL_START:
                approve.append({**base, "kind": "manual_start",
                                "summary": "Run the generated code on this PC to produce real results. "
                                           "This step never starts by itself."})
    # Research loops: finished (accept the result), paused between rounds, failed, or working.
    for p in projects:
        for lp in loops.list_view(store, p["id"]):
            base = {"kind": "loop", "project_id": p["id"], "project": p["title"], "loop_id": lp["id"],
                    "paper": lp["goal"], "stage": f"{lp['label']} · round {lp['round']}", "loop_type": lp["type"]}
            if lp["status"] == "finished" and not lp["accepted"]:
                approve.append({**base, "loop_state": "finished", "summary": "Loop finished — " + (lp["stop_reason"] or "")})
            elif lp["status"] == "paused":
                approve.append({**base, "loop_state": "paused", "summary": lp["paused_reason"]})
            elif lp["status"] == "failed":
                retry.append({**base, "status": "failed", "error": lp["stop_reason"]})
            elif lp["status"] == "running":
                running.append({**base, "status": "running", "stage": f"{lp['label']} · round {lp['round']} · "
                                f"{loops.MOVE_LABELS.get(lp['move'] or '', '')}"})
    # Director plans proposed but not yet approved.
    for c in store.all("SELECT DISTINCT r.conversation_id, c.project_id, c.title, p.title project "
                       "FROM runs r JOIN conversations c ON c.id=r.conversation_id JOIN projects p ON p.id=c.project_id "
                       "WHERE r.kind='director' AND r.status='succeeded' AND p.status='active'"):
        if store.one("SELECT id FROM runs WHERE conversation_id=? AND kind='plan'", (c["conversation_id"],)):
            continue
        plan = director.load_plan(c["project_id"], c["conversation_id"])
        if plan and plan.get("steps"):
            approve.append({"kind": "plan", "project_id": c["project_id"], "project": c["project"],
                            "conversation_id": c["conversation_id"], "paper": c["title"],
                            "stage": "Research Director plan", "summary": plan.get("summary"),
                            "steps": [s.get("title") or s.get("name") for s in plan["steps"]],
                            "blocked": any(not s.get("known") for s in plan["steps"])})
    # Other agent runs that are working now or failed in the last day (chat, recipes, tools).
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="milliseconds")
    for r in store.all("SELECT r.id, r.kind, r.status, r.error, r.project_id, r.conversation_id, c.title, p.title project "
                       "FROM runs r JOIN conversations c ON c.id=r.conversation_id JOIN projects p ON p.id=r.project_id "
                       "WHERE r.kind NOT LIKE 'paper:%' AND r.kind NOT LIKE 'loop:%' AND (r.status IN ('queued','running') OR "
                       "(r.status='failed' AND r.finished_at > ?)) ORDER BY r.created_at DESC LIMIT 30", (cutoff,)):
        item = {"kind": "run", "run_id": r["id"], "project_id": r["project_id"], "project": r["project"],
                "conversation_id": r["conversation_id"], "paper": r["title"], "stage": r["title"]}
        if r["status"] == "failed":
            retry.append({**item, "status": "failed", "error": r["error"]})
        else:
            running.append({**item, "status": r["status"]})
    # Memories waiting for the user: proposed by an agent, or flagged as a possible conflict.
    for m in store.all("SELECT m.id, m.project_id, m.domain, m.title, m.content, m.status, m.conflict_with, "
                       "p.title project FROM memory_items m LEFT JOIN projects p ON p.id=m.project_id "
                       "WHERE m.status IN ('proposed','needs_review') ORDER BY m.created_at DESC LIMIT 50"):
        other = store.one("SELECT title FROM memory_items WHERE id=?", (m["conflict_with"],)) if m["conflict_with"] else None
        approve.append({"kind": "memory", "memory_id": m["id"], "project_id": m["project_id"],
                        "project": m["project"] or "All projects", "paper": m["title"],
                        "stage": f"Memory · {m['domain']}" + (" · possible conflict" if m["status"] == "needs_review" else ""),
                        "summary": (f"Looks like it conflicts with: {other['title']}. " if other else "") + m["content"][:400]})
    hidden = dismissed()
    for x in approve + retry:
        x["key"] = _key(x)
    approve = [x for x in approve if x["key"] not in hidden]
    retry = [x for x in retry if x["key"] not in hidden]
    return {"approve": approve, "retry": retry, "running": running,
            "counts": {"approve": len(approve), "retry": len(retry), "running": len(running)}}

