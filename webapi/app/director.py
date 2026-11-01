"""Research Director: turns a research goal into a plan of tool runs, executed only after approval.

1. A Director turn is a Claude Code run with an extra system prompt listing every research
   tool. For goals that need tools it writes a plan file instead of doing the work itself.
2. The user reads the plan in the chat and approves it (the approval gate).
3. The executor runs the steps one at a time in the same chat, each through the normal
   workflow runner, and stops at the first failure or when the user stops the plan.
"""
from __future__ import annotations

import json
import threading
import time

from . import claude_runner, workflows, workspace
from .db import Store, TERMINAL_STATES, new_id, now


def plan_path(conversation_id: str) -> str:
    return f"director/plan_{conversation_id}.json"


def _catalog() -> str:
    lines = []
    for w in workflows.WORKFLOWS:
        if w["engine"] == "cli" and w["id"] in {"protocol_lock"}:
            continue  # human-only gate: never planned automatically
        fields = ", ".join(f"{i['name']} ({i['kind']}{', required' if i.get('required') else ''}"
                           f"{', one of ' + '/'.join(i['options']) if i.get('options') else ''})" for i in w["inputs"])
        lines.append(f"- `{w['id']}` — {w['name']}: {w['description']} Inputs: {fields or 'none'}.")
    return "\n".join(lines)


DIRECTOR_SYSTEM = f"""You are the Research Director of ResearchLedger. You coordinate specialist research agents.

When the user's request is a question you can answer directly, or a small task, just do it.
When it needs one or more of the research tools below, do NOT do that work yourself. Instead:
1. Read memory/research_memory.md and look at the workspace files you need to plan well.
2. Write the plan file named in the user's message, exactly in this JSON shape:
   {{"goal": "...", "summary": "one paragraph in plain language",
     "steps": [{{"workflow": "<tool id>", "title": "short title", "why": "why this step",
                "values": {{"<input name>": "<value>"}}}}]}}
   Use only tool ids from the list. File inputs are workspace-relative paths; a later step may use a
   file an earlier step will produce (name it as that tool's output). Keep plans to 1–6 steps, in order.
3. Explain the plan to the user in a short numbered list and say that nothing runs until they press Approve.

Research tools:
{_catalog()}
"""
claude_runner.DIRECTOR_SYSTEM = DIRECTOR_SYSTEM


def start_turn(store: Store, conversation_id: str, prompt: str, model: str | None) -> dict:
    conv = store.one("SELECT * FROM conversations WHERE id=?", (conversation_id,))
    rid, ts = new_id("run"), now()
    full = (f"{prompt}\n\n[Research Director: if this needs research tools, write the plan to "
            f"`{plan_path(conversation_id)}`.]")
    store.exec("INSERT INTO runs(id,project_id,conversation_id,kind,prompt,status,provider,model,created_at) "
               "VALUES (?,?,?,?,?,?,?,?,?)", (rid, conv["project_id"], conversation_id, "director", full, "queued",
                                               "claude_code_cli", model, ts))
    if conv["title"] == "New chat":
        store.exec("UPDATE conversations SET title=? WHERE id=?", (" ".join(prompt.split())[:60], conversation_id))
    store.exec("UPDATE conversations SET updated_at=? WHERE id=?", (ts, conversation_id))
    claude_runner.start_run(store, rid)
    return store.one("SELECT * FROM runs WHERE id=?", (rid,))


def load_plan(project_id: str, conversation_id: str) -> dict | None:
    p = workspace.project_root(project_id) / plan_path(conversation_id)
    if not p.is_file():
        return None
    try:
        plan = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"error": "plan file is not valid JSON", "steps": []}
    steps = plan.get("steps") if isinstance(plan.get("steps"), list) else []
    for s in steps:
        w = workflows.BY_ID.get(str(s.get("workflow")))
        s["known"] = bool(w) and s.get("workflow") != "protocol_lock"
        s["name"] = w["name"] if w else s.get("workflow")
    plan["steps"] = steps[:6]
    return plan


def approve(store: Store, project_id: str, conversation_id: str) -> dict:
    plan = load_plan(project_id, conversation_id)
    if not plan or not plan["steps"]:
        raise workflows.WorkflowError("there is no plan to approve in this chat")
    unknown = [s.get("workflow") for s in plan["steps"] if not s["known"]]
    if unknown:
        raise workflows.WorkflowError(f"plan uses unknown or human-only tools: {', '.join(map(str, unknown))}")
    busy = store.one("SELECT id FROM runs WHERE conversation_id=? AND status IN ('queued','running')", (conversation_id,))
    if busy:
        raise workflows.WorkflowError(f"run {busy['id']} is still active in this chat")
    rid, ts = new_id("run"), now()
    titles = "\n".join(f"{i + 1}. {s.get('title') or s['name']}" for i, s in enumerate(plan["steps"]))
    store.exec("INSERT INTO runs(id,project_id,conversation_id,kind,prompt,status,provider,created_at,started_at) "
               "VALUES (?,?,?,?,?,?,?,?,?)", (rid, project_id, conversation_id, "plan", f"Approved plan:\n{titles}",
                                               "running", "director", ts, ts))
    store.add_event(rid, "plan", {"goal": plan.get("goal"), "steps": [
        {"index": i, "title": s.get("title") or s["name"], "workflow": s["workflow"], "status": "pending"}
        for i, s in enumerate(plan["steps"])]})
    store.log_activity(project_id, "plan_approved", rid)
    threading.Thread(target=_execute, args=(store, rid, project_id, conversation_id, plan["steps"]),
                     daemon=True, name=f"plan-{rid}").start()
    return store.one("SELECT * FROM runs WHERE id=?", (rid,))


def _execute(store: Store, plan_run: str, project_id: str, conversation_id: str, steps: list[dict]) -> None:
    started = time.monotonic()
    for i, step in enumerate(steps):
        if store.one("SELECT status FROM runs WHERE id=?", (plan_run,))["status"] in TERMINAL_STATES:
            return  # stopped by the user
        title = step.get("title") or step["name"]
        store.add_event(plan_run, "plan_step", {"index": i, "status": "running", "title": title})
        try:
            child = workflows.launch(store, project_id, step["workflow"], step.get("values") or {}, conversation_id)
        except (workflows.WorkflowError, workspace.PathError) as exc:
            _finish(store, plan_run, i, title, "failed", f"Step {i + 1} ({title}) could not start: {exc}", started)
            return
        store.add_event(plan_run, "plan_step", {"index": i, "status": "running", "title": title, "run_id": child["run_id"]})
        while True:
            status = store.one("SELECT status, error FROM runs WHERE id=?", (child["run_id"],))
            if status["status"] in TERMINAL_STATES:
                break
            if store.one("SELECT status FROM runs WHERE id=?", (plan_run,))["status"] in TERMINAL_STATES:
                claude_runner.cancel_run(store, child["run_id"])
                return
            time.sleep(1)
        if status["status"] != "succeeded":
            _finish(store, plan_run, i, title, "failed",
                    f"Step {i + 1} ({title}) {status['status']}: {status['error'] or ''}".strip(), started,
                    run_id=child["run_id"])
            return
        store.add_event(plan_run, "plan_step", {"index": i, "status": "succeeded", "title": title, "run_id": child["run_id"]})
    _finish(store, plan_run, None, None, "succeeded", None, started)


def _finish(store, plan_run, index, title, status, error, started, run_id=None):
    if index is not None:
        store.add_event(plan_run, "plan_step", {"index": index, "status": status, "title": title, "run_id": run_id})
    if error:
        store.add_event(plan_run, "error", {"text": error})
    store.update_run(plan_run, status=status, finished_at=now(), error=error,
                     duration_ms=int((time.monotonic() - started) * 1000))
    store.add_event(plan_run, "done", {"status": status})


def stop(store: Store, plan_run: str) -> bool:
    run = store.one("SELECT * FROM runs WHERE id=? AND kind='plan'", (plan_run,))
    if not run or run["status"] in TERMINAL_STATES:
        return False
    store.update_run(plan_run, status="cancelled", finished_at=now(), error="stopped by user")
    store.add_event(plan_run, "status", {"text": "Plan stopped by user"})
    store.add_event(plan_run, "done", {"status": "cancelled"})
    return True
