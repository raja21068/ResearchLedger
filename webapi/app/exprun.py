"""Server-side execution of experiment scripts for the experiment loop.

The agent writes the code; the server runs it, after the user's click, so the provenance of every result is known
first-hand: which script (and its SHA-256) ran with which command, its exit code and runtime, and which
`results/<slot>.json` files it wrote during that run. A results file that was not written by the run does not count.

Only `python <script under the workspace> [args]` commands are accepted; `python` is replaced by the configured
interpreter (RL_EXP_PYTHON, default: the server's own Python).
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import experiments, versions
from .db import Store, now

PROVIDER = "server_exec"
_procs: dict[str, subprocess.Popen] = {}
_cancelled: set[str] = set()
_lock = threading.Lock()


def python_exe() -> str:
    return os.environ.get("RL_EXP_PYTHON") or sys.executable


def parse_command(root: Path, command: str) -> tuple[list[str] | None, str | None]:
    """Validate `python <script.py> [args]`; return (argv relative to root, error)."""
    try:
        argv = shlex.split(command or "", posix=True)
    except ValueError as exc:
        return None, f"cannot parse command ({exc})"
    if len(argv) < 2 or argv[0] not in {"python", "python3", "py"}:
        return None, "command must be `python <script.py> [args]`"
    script = argv[1].replace("\\", "/")
    target = (root / script).resolve()
    if not script.endswith(".py") or root.resolve() not in target.parents:
        return None, f"script {argv[1]} must be a .py file inside the workspace"
    return [argv[0], script, *argv[2:]], None


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def run_jobs(store: Store, run_id: str, root: Path, jobs: list[dict], log_dir: Path, out_json: Path) -> None:
    """Run each job in order and write run_log.json. jobs: [{id, argv, slots, timeout_s}]."""
    store.update_run(run_id, status="running", started_at=now())
    project_id = store.one("SELECT project_id FROM runs WHERE id=?", (run_id,))["project_id"]
    versions.safe_sync(store, project_id, "external")
    store.add_event(run_id, "status", {"text": f"Running {len(jobs)} experiment(s) on the server"})
    log_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for job in jobs:
        if run_id in _cancelled:
            break
        script = root / job["argv"][1]
        rec = {"id": job["id"], "command": " ".join(job["argv"]), "script": job["argv"][1],
               "script_sha256": _sha(script), "started_at": now(), "slots": {}}
        log_path = log_dir / f"run_{job['id']}.log"
        t0 = time.time()
        try:
            with log_path.open("w", encoding="utf-8", errors="replace") as log:
                proc = subprocess.Popen([python_exe(), *job["argv"][1:]], cwd=root, stdout=log,
                                        stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
                with _lock:
                    _procs[run_id] = proc
                try:
                    rec["exit_code"] = proc.wait(timeout=job["timeout_s"])
                    rec["timed_out"] = False
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    rec["exit_code"], rec["timed_out"] = None, True
        except OSError as exc:
            rec["exit_code"], rec["timed_out"], rec["error"] = None, False, f"could not start: {exc}"
        finally:
            with _lock:
                _procs.pop(run_id, None)
        rec["seconds"] = round(time.time() - t0, 1)
        rec["log"] = log_path.relative_to(root).as_posix()
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-3000:] if log_path.is_file() else ""
        rec["log_tail"] = tail
        for slot in job["slots"]:
            p = root / "results" / f"{slot}.json"
            if not p.is_file():
                rec["slots"][slot] = {"ok": False, "error": "no results file written"}
                continue
            if p.stat().st_mtime < t0 - 1:
                rec["slots"][slot] = {"ok": False, "error": "results file is older than this run (not written by it)"}
                continue
            data, err = experiments._read_result(p)
            if err:
                rec["slots"][slot] = {"ok": False, "error": err}
            else:
                rec["slots"][slot] = {"ok": True, "value": data["value"], "unit": data.get("unit"),
                                      "seed": data.get("seed"), "sha256": _sha(p), "file": f"results/{slot}.json"}
        rec["ok"] = rec.get("exit_code") == 0 and all(s["ok"] for s in rec["slots"].values())
        results.append(rec)
        store.add_event(run_id, "status", {"text": f"{job['id']}: exit {rec.get('exit_code')}, "
                                                   f"{sum(s['ok'] for s in rec['slots'].values())}/{len(job['slots'])} "
                                                   f"result(s) in {rec['seconds']}s"})
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"python": python_exe(), "finished_at": now(), "jobs": results}, indent=2),
                        encoding="utf-8")
    versions.safe_sync(store, project_id, "server_exec", run_id)
    if run_id in _cancelled:
        _cancelled.discard(run_id)
        return  # cancel() already marked the run
    store.update_run(run_id, status="succeeded", finished_at=now())
    store.add_event(run_id, "done", {"status": "succeeded"})


def start(store: Store, run_id: str, root: Path, jobs: list[dict], log_dir: Path, out_json: Path) -> None:
    threading.Thread(target=run_jobs, args=(store, run_id, root, jobs, log_dir, out_json), daemon=True,
                     name=f"exp-{run_id}").start()


def cancel(store: Store, run_id: str) -> bool:
    run = store.one("SELECT status, provider FROM runs WHERE id=?", (run_id,))
    if not run or run["provider"] != PROVIDER or run["status"] not in {"queued", "running"}:
        return False
    with _lock:
        _cancelled.add(run_id)
        proc = _procs.get(run_id)
    store.update_run(run_id, status="cancelled", finished_at=now(), error="cancelled by user")
    store.add_event(run_id, "done", {"status": "cancelled"})
    if proc:
        proc.kill()
    return True
