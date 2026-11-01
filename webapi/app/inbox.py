"""Approvals inbox: everything across all projects that is waiting for one click from the user.

Human-in-the-loop in one place: paper stages to approve, Director plans to approve,
failed steps to retry, and what is running right now. Read-only; the actions reuse the
existing endpoints (approve stage, run stage with feedback, approve plan).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import director, paper_studio
from .db import Store


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
                       "WHERE r.kind NOT LIKE 'paper:%' AND (r.status IN ('queued','running') OR "
                       "(r.status='failed' AND r.finished_at > ?)) ORDER BY r.created_at DESC LIMIT 30", (cutoff,)):
        item = {"kind": "run", "run_id": r["id"], "project_id": r["project_id"], "project": r["project"],
                "conversation_id": r["conversation_id"], "paper": r["title"], "stage": r["title"]}
        if r["status"] == "failed":
            retry.append({**item, "status": "failed", "error": r["error"]})
        else:
            running.append({**item, "status": r["status"]})
    return {"approve": approve, "retry": retry, "running": running,
            "counts": {"approve": len(approve), "retry": len(retry), "running": len(running)}}

