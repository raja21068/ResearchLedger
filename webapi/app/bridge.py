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
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path

from . import memory, workspace
from .config import settings
from .db import Store, TERMINAL_STATES, now

_lock = threading.Lock()
_last_poll: float | None = None

STALE_S = 15 * 60       # a claimed run with no sign of life for this long goes back to the queue
MAX_REQUEUES = 2        # then it is marked failed instead of looping forever
POLL_FRESH_S = 90
_claims: dict[str, dict] = {}  # run_id -> {"token": str, "at": last sign of life (epoch seconds)}


class ClaimError(ValueError):
    """A worker used a run it no longer owns (the run was re-queued)."""


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


def _last_activity(store: Store, run: dict) -> float:
    ev = store.one("SELECT MAX(ts) t FROM run_events WHERE run_id=?", (run["id"],))
    stamps = [_claims.get(run["id"], {}).get("at", 0.0)]
    for iso in (ev and ev["t"], run["started_at"]):
        if iso:
            stamps.append(datetime.fromisoformat(iso).timestamp())
    return max(stamps)


def requeue_stale(store: Store, now_ts: float | None = None, stale_s: float = STALE_S) -> list[str]:
    """Put runs claimed by a worker that went silent back in the queue (or fail them after MAX_REQUEUES)."""
    t = now_ts if now_ts is not None else time.time()
    moved = []
    with _lock:
        for run in store.all("SELECT * FROM runs WHERE status='running' AND provider='claude_code_cli'"):
            if run["id"] not in _claims or t - _last_activity(store, run) < stale_s:
                continue
            _claims.pop(run["id"], None)
            previous = sum(1 for e in store.all("SELECT payload FROM run_events WHERE run_id=? AND kind='status'",
                                                (run["id"],)) if "Re-queued" in e["payload"])
            if previous >= MAX_REQUEUES:
                store.update_run(run["id"], status="failed", finished_at=now(),
                                 error="The Claude app worker stopped responding (re-queued twice).")
                store.add_event(run["id"], "error", {"text": "The Claude app worker stopped responding; giving up after "
                                                             f"{MAX_REQUEUES} re-queues."})
                store.add_event(run["id"], "done", {"status": "failed"})
            else:
                store.update_run(run["id"], status="queued", started_at=None)
                store.add_event(run["id"], "status",
                                {"text": f"Re-queued: the worker was silent for {int(stale_s // 60)} minutes"})
            moved.append(run["id"])
    return moved


def status(store: Store) -> dict:
    requeue_stale(store)
    queued = store.one("SELECT COUNT(*) n FROM runs WHERE status='queued' AND provider='claude_code_cli'")["n"]
    busy = None
    if _claims:
        busy = store.one("SELECT id FROM runs WHERE status='running' AND provider='claude_code_cli' AND id IN (%s)"
                         % ",".join("?" * len(_claims)), tuple(_claims))
    age = None if _last_poll is None else round(time.time() - _last_poll)
    polling = age is not None and age < POLL_FRESH_S
    state = "busy" if busy else "free" if polling else "offline"
    # A busy worker is not polling, so it must still count as connected.
    return {"executor": executor(), "worker_connected": state != "offline", "worker_state": state,
            "busy_run_id": busy["id"] if busy else None, "last_poll_seconds_ago": age, "queued": queued,
            "stale_after_s": STALE_S}


def queue(store: Store, run_id: str) -> None:
    store.add_event(run_id, "status", {"text": "Waiting for the Claude app worker (/rl-worker)…"})


def claim(store: Store) -> dict | None:
    """Atomically take the oldest queued agent run and return everything the worker needs."""
    global _last_poll
    _last_poll = time.time()
    requeue_stale(store)
    with _lock:
        run = store.one("SELECT * FROM runs WHERE status='queued' AND provider='claude_code_cli' "
                        "ORDER BY created_at LIMIT 1")
        if not run:
            return None
        store.update_run(run["id"], status="running", started_at=now())
        token = secrets.token_hex(8)
        _claims[run["id"]] = {"token": token, "at": time.time()}
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
    from . import prefs
    instructions = SYSTEM_PROMPT + prefs.system_block() + ("\n\n" + DIRECTOR_SYSTEM if run["kind"] == "director" else "")
    return {"run_id": run["id"], "claim": token, "kind": run["kind"], "project": project["title"],
            "workspace": str(workspace.project_root(run["project_id"])),
            "conversation": conv["title"], "instructions": instructions,
            "earlier_turns": history, "task": run["prompt"], "model_hint": run["model"]}


def _check_claim(run_id: str, claim: str | None) -> None:
    held = _claims.get(run_id)
    if claim and held and claim != held["token"]:
        raise ClaimError("this run was re-queued and now belongs to another worker")
    if held:
        held["at"] = time.time()


def add_event(store: Store, run_id: str, kind: str, text: str, claim: str | None = None) -> None:
    run = store.one("SELECT status FROM runs WHERE id=?", (run_id,))
    if not run or run["status"] != "running":
        raise ClaimError("run is not running (it may have been re-queued)")
    _check_claim(run_id, claim)
    if kind == "ping":
        return  # heartbeat only
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


def complete(store: Store, run_id: str, summary: str, failed: bool = False, claim: str | None = None) -> dict:
    run = store.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not run:
        raise ValueError("run not found")
    if run["status"] in TERMINAL_STATES:
        return run
    if run["status"] == "queued":
        raise ClaimError("this run was re-queued; its result was not accepted")
    _check_claim(run_id, claim)
    _claims.pop(run_id, None)
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
