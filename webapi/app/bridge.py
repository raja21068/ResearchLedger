"""Claude app bridge: let the logged-in Claude desktop app do the agent work.

Instead of starting `claude.exe` (which needs its own login), runs stay queued until a
Claude Code session in the Claude app's Code tab claims them. That session runs the
`/rl-worker` command (`.claude/commands/rl-worker.md`), which loops:

    python webapi/bridge_cli.py next      -> claim the next task (long-poll)
    ...do the work in the project workspace with its own tools...
    python webapi/bridge_cli.py done ...  -> send the reply back

The website shows the same run, events and files as for the CLI executor.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from . import memory, workspace
from .config import settings
from .db import Store, TERMINAL_STATES, now

_lock = threading.Lock()
_last_poll: float | None = None


def _settings_file() -> Path:
    return settings.data_dir / "settings.json"


def executor() -> str:
    """'bridge' (Claude app worker) or 'cli' (claude.exe). Env RL_EXECUTOR wins, then the Settings page."""
    import os
    if os.environ.get("RL_EXECUTOR") in {"bridge", "cli"}:
        return os.environ["RL_EXECUTOR"]
    try:
        return json.loads(_settings_file().read_text(encoding="utf-8")).get("executor", "bridge")
    except (OSError, json.JSONDecodeError):
        return "bridge"


def set_executor(value: str) -> None:
    p = _settings_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data["executor"] = value
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def status(store: Store) -> dict:
    queued = store.one("SELECT COUNT(*) n FROM runs WHERE status='queued' AND provider='claude_code_cli'")["n"]
    age = None if _last_poll is None else round(time.time() - _last_poll)
    return {"executor": executor(), "worker_connected": age is not None and age < 90,
            "last_poll_seconds_ago": age, "queued": queued}


def queue(store: Store, run_id: str) -> None:
    store.add_event(run_id, "status", {"text": "Waiting for the Claude app worker (/rl-worker)…"})


def claim(store: Store) -> dict | None:
    """Atomically take the oldest queued agent run and return everything the worker needs."""
    global _last_poll
    _last_poll = time.time()
    with _lock:
        run = store.one("SELECT * FROM runs WHERE status='queued' AND provider='claude_code_cli' "
                        "ORDER BY created_at LIMIT 1")
        if not run:
            return None
        store.update_run(run["id"], status="running", started_at=now())
    store.add_event(run["id"], "status", {"text": "Claude app worker started the task"})
    from .claude_runner import SYSTEM_PROMPT
    from . import director  # noqa: F401  (fills DIRECTOR_SYSTEM)
    from .claude_runner import DIRECTOR_SYSTEM
    conv = store.one("SELECT * FROM conversations WHERE id=?", (run["conversation_id"],))
    project = store.one("SELECT * FROM projects WHERE id=?", (run["project_id"],))
    history = []
    if run["kind"] in {"claude_code", "director"}:
        for r in store.all("SELECT prompt, result_text, status FROM runs WHERE conversation_id=? AND id<>? "
                           "AND created_at < ? ORDER BY created_at DESC LIMIT 6",
                           (run["conversation_id"], run["id"], run["created_at"])):
            history.append({"user": r["prompt"][:4000], "assistant": (r["result_text"] or "")[:4000],
                            "status": r["status"]})
        history.reverse()
    instructions = SYSTEM_PROMPT + ("\n\n" + DIRECTOR_SYSTEM if run["kind"] == "director" else "")
    return {"run_id": run["id"], "kind": run["kind"], "project": project["title"],
            "workspace": str(workspace.project_root(run["project_id"])),
            "conversation": conv["title"], "instructions": instructions,
            "earlier_turns": history, "task": run["prompt"], "model_hint": run["model"]}


def add_event(store: Store, run_id: str, kind: str, text: str) -> None:
    run = store.one("SELECT status FROM runs WHERE id=?", (run_id,))
    if not run or run["status"] != "running":
        raise ValueError("run is not running")
    if kind == "todos":
        items = [{"content": line.lstrip("-*[]xX ").strip(), "status":
                  "completed" if line.strip().startswith(("[x]", "[X]", "- [x]")) else
                  "in_progress" if line.strip().startswith((">", "- >")) else "pending"}
                 for line in text.splitlines() if line.strip()]
        store.add_event(run_id, "todos", {"items": items[:30]})
    elif kind == "step":
        store.add_event(run_id, "tool_use", {"id": f"b{time.time_ns()}", "name": "Step", "target": text[:300]})
    else:
        store.add_event(run_id, "assistant_text", {"text": text[:20000]})


def complete(store: Store, run_id: str, summary: str, failed: bool = False) -> dict:
    run = store.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not run:
        raise ValueError("run not found")
    if run["status"] in TERMINAL_STATES:
        return run
    started = run["started_at"] or run["created_at"]
    from datetime import datetime
    since = datetime.fromisoformat(started).timestamp() - 1
    root = workspace.project_root(run["project_id"])
    produced = []
    for rel in workspace.changed_since(run["project_id"], since):
        p = root / rel
        store.exec("INSERT INTO artifacts(run_id, project_id, path, sha256, size, change, created_at) "
                   "VALUES (?,?,?,?,?,?,?)", (run_id, run["project_id"], rel, workspace.sha256(p),
                                              p.stat().st_size, "written", now()))
        if not workspace.is_build_output(rel) and rel != memory.MEMORY_PATH:
            produced.append(rel)
    if summary.strip():
        store.add_event(run_id, "assistant_text", {"text": summary[:20000]})
    if produced:
        store.add_event(run_id, "artifacts", {"files": [{"path": p, "change": "written"} for p in produced]})
    status_ = "failed" if failed else "succeeded"
    store.update_run(run_id, status=status_, finished_at=now(), result_text=summary[:20000],
                     error=summary[:2000] if failed else None)
    store.add_event(run_id, "result", {"is_error": failed, "text": summary[:2000], "cost_usd": None})
    store.add_event(run_id, "done", {"status": status_})
    conv = store.one("SELECT title FROM conversations WHERE id=?", (run["conversation_id"],))
    memory.append_run(run["project_id"], conv["title"], run_id, status_, summary, produced)
    store.log_activity(run["project_id"], f"run_{status_}", run_id)
    return store.one("SELECT * FROM runs WHERE id=?", (run_id,))
