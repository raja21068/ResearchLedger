"""Mission control (docs/RESEARCHLEDGER_OS_BLUEPRINT.md §5 P4): every task in one honest view.

Read-only. A display state is derived from what the server actually recorded:
- queued: waiting for the Claude app worker, or for another agent task in the same project to finish;
- running: an agent or a server run is working (with the last thing it reported and, for the app worker, the age of
  its last heartbeat);
- awaiting_approval: nothing runs until you decide (Decisions inbox);
- completed / failed / cancelled;
- interrupted: the server restarted while it ran. Nothing is retried silently; the place it belongs to offers
  "run again".
Only controls the runtime supports are offered: cancel for queued or running tasks. Agents cannot be paused.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from . import bridge, exprun, inbox, paper_studio
from .db import Store

RESTART_ERROR = "server restarted while run was active"
STAGE_WORDS = {"attack": "paper search", "score": "scoring", "redesign": "redesign", "design": "plan", "code": "code",
               "run": "run on this computer", "analyze": "analysis", "review": "review", "fix": "fix",
               "verify": "verify"}


def label(kind: str) -> str:
    """'loop:idea_forge:attack' -> 'Idea loop · paper search'; 'paper:write' -> 'Paper · write'."""
    parts = (kind or "").split(":")
    if parts[0] == "loop" and len(parts) == 3:
        name = {"idea_forge": "Idea loop", "experiment": "Experiment loop", "review_fix": "Review-and-fix loop"}.get(
            parts[1], parts[1].replace("_", " ").capitalize())
        return f"{name} · {STAGE_WORDS.get(parts[2], parts[2])}"
    if parts[0] in {"paper", "workflow", "recipe", "tool"} and len(parts) == 2:
        return f"{parts[0].capitalize()} · {parts[1].replace('_', ' ')}"
    return {"claude_code": "Chat", "director": "Research Director", "plan": "Director plan step",
            "repeat": "Repeat run"}.get(kind, (kind or "task").replace("_", " ").capitalize())


def _state(r: dict) -> str:
    if r["status"] == "failed" and (r.get("error") or "").startswith(RESTART_ERROR):
        return "interrupted"
    return {"succeeded": "completed"}.get(r["status"], r["status"])


def _link(r: dict) -> str:
    kind = r["kind"] or ""
    if kind.startswith("loop:"):
        return f"/loops?project={r['project_id']}"
    if kind.startswith("paper:"):
        return f"/projects/{r['project_id']}/paper"
    if r["provider"] == exprun.PROVIDER:
        return f"/projects/{r['project_id']}/lab"
    return f"/projects/{r['project_id']}?conv={r['conversation_id']}"


def _last_event(store: Store, run_id: str) -> dict | None:
    ev = store.one("SELECT ts, kind, payload FROM run_events WHERE run_id=? AND kind IN "
                   "('status','assistant_text','tool_use','job','error') ORDER BY id DESC LIMIT 1", (run_id,))
    if not ev:
        return None
    p = json.loads(ev["payload"])
    text = p.get("text") or (f"{p.get('id')}: {p.get('state')}" if ev["kind"] == "job" else None) \
        or (f"{p.get('name')} {p.get('target', '')}".strip() if ev["kind"] == "tool_use" else None)
    return {"ts": ev["ts"], "text": (text or ev["kind"])[:300]}


def _secs(a: str | None, b: str | None = None) -> int | None:
    if not a:
        return None
    end = datetime.fromisoformat(b).timestamp() if b else time.time()
    return max(0, int(end - datetime.fromisoformat(a).timestamp()))


def overview(store: Store, recent_hours: int = 24) -> dict:
    claims = dict(bridge._claims)
    now_ts = time.time()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=recent_hours)).isoformat(timespec="milliseconds")
    rows = store.all(
        "SELECT r.id, r.kind, r.status, r.provider, r.error, r.created_at, r.started_at, r.finished_at, r.project_id, "
        "r.conversation_id, p.title project FROM runs r JOIN projects p ON p.id=r.project_id "
        "WHERE r.status IN ('queued','running') OR r.created_at > ? ORDER BY r.created_at DESC LIMIT 300", (cutoff,))
    busy_projects = {r["project_id"] for r in rows if r["status"] == "running" and r["provider"] == "claude_code_cli"}
    worker = bridge.status(store)
    tasks = []
    for r in rows:
        t = {"id": r["id"], "label": label(r["kind"]), "kind": r["kind"], "project_id": r["project_id"],
             "project": r["project"], "state": _state(r), "agent": r["provider"] != exprun.PROVIDER,
             "created_at": r["created_at"], "started_at": r["started_at"], "finished_at": r["finished_at"],
             "elapsed_s": _secs(r["started_at"], r["finished_at"]) if r["started_at"] else None,
             "error": r["error"], "link": _link(r), "last": _last_event(store, r["id"]),
             "can_cancel": r["status"] in {"queued", "running"}}
        if r["status"] == "queued":
            if r["provider"] == "claude_code_cli" and worker["executor"] == "bridge":
                t["waiting_for"] = ("another agent task in this project" if r["project_id"] in busy_projects
                                    else "the Claude app worker (/rl-worker)" if not worker["worker_connected"]
                                    else "its turn in the queue")
            t["waiting_s"] = _secs(r["created_at"])
        if r["id"] in claims:
            t["heartbeat_s"] = int(now_ts - claims[r["id"]]["at"])
        if r["provider"] == exprun.PROVIDER and r["status"] in {"queued", "running"}:
            jobs = {}
            for e in store.all("SELECT payload FROM run_events WHERE run_id=? AND kind='job' ORDER BY id", (r["id"],)):
                p = json.loads(e["payload"])
                jobs[p["id"]] = {**jobs.get(p["id"], {}), **p}
            t["jobs"] = list(jobs.values())
        tasks.append(t)
    needs = inbox.build(store)
    pipelines = []
    for p in store.all("SELECT id, title FROM projects WHERE status='active' ORDER BY updated_at DESC LIMIT 12"):
        v = paper_studio.view(store, p["id"])
        if v:
            pipelines.append({"project_id": p["id"], "project": p["title"], "topic": v.get("topic"),
                              "stages": [{"id": s["id"], "title": s["title"], "status": s["status"]} for s in v["stages"]]})
    groups = {k: [t for t in tasks if t["state"] == k] for k in
              ("running", "queued", "interrupted", "failed", "completed", "cancelled")}
    return {"worker": worker, "needs_you": {"count": needs["counts"]["approve"], "items": needs["approve"][:8]},
            "tasks": groups, "pipelines": pipelines,
            "counts": {k: len(v) for k, v in groups.items()} | {"needs_you": needs["counts"]["approve"]},
            "recent_hours": recent_hours}
