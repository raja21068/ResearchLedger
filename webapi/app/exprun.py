"""The one execution service for experiment code (experiment loops and Paper Studio).

The agent writes the code; the server runs it, after the user's click, so the provenance of every result is known
first-hand: which script (and its SHA-256) ran with which command, its exit code and runtime, and which
`results/<slot>.json` files it wrote during that run. A results file that was not written by the run does not count.

Only `python <script under the workspace> [args]` commands are accepted; `python` is replaced by the configured
interpreter (RL_EXP_PYTHON, default: the server's own Python). The only other job is installing
`code/requirements.txt` with pip, when the user approved it. Runner: this computer (host); every run_log.json says so.
Agents never execute experiment code themselves: they plan jobs (`code/jobs.json`, or the loop's exp_plan.json) and
the user approves the run here.
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
RUNNER = "host"  # see docs/STORAGE_DATABASE_ARCHITECTURE.md §8: a Docker runner waits for the user's decision
MAX_JOB_MINUTES = 30
JOBS_FILE = "code/jobs.json"
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
        script_rel = job.get("script", job["argv"][1])
        rec = {"id": job["id"], "command": " ".join(job["argv"]), "script": script_rel,
               "script_sha256": _sha(root / script_rel), "started_at": now(), "slots": {}, "runner": RUNNER}
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
        if job.get("required") and not rec["ok"]:
            store.add_event(run_id, "status", {"text": f"{job['id']} failed; the remaining jobs were not started"})
            break
        store.add_event(run_id, "status", {"text": f"{job['id']}: exit {rec.get('exit_code')}, "
                                                   f"{sum(s['ok'] for s in rec['slots'].values())}/{len(job['slots'])} "
                                                   f"result(s) in {rec['seconds']}s"})
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"python": python_exe(), "runner": RUNNER, "run_id": run_id, "finished_at": now(),
                                    "jobs": results}, indent=2), encoding="utf-8")
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


def plan_from_file(root: Path, declared_slots: set[str] | None = None) -> tuple[list[dict], list[str]]:
    """Read and check `code/jobs.json`: {"jobs": [{"id", "command", "slots": [...], "timeout_minutes"}]}.
    Returns (jobs ready for run_jobs, problems in plain words). Nothing runs here."""
    path = root / JOBS_FILE
    if not path.is_file():
        return [], [f"{JOBS_FILE} is missing: the Code stage must list the commands to run"]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [f"{JOBS_FILE} is not valid JSON ({exc.msg}, line {exc.lineno})"]
    items = raw.get("jobs") if isinstance(raw, dict) else None
    if not isinstance(items, list) or not items:
        return [], [f"{JOBS_FILE} must be {{\"jobs\": [...]}} with at least one job"]
    jobs, problems, ids, seen = [], [], set(), set()
    for i, e in enumerate(items, 1):
        if not isinstance(e, dict):
            problems.append(f"job {i}: not an object")
            continue
        jid = str(e.get("id") or f"J{i}").strip()
        if jid in ids or not jid.replace("_", "").replace("-", "").isalnum():
            problems.append(f"job {i}: id {jid!r} is repeated or has odd characters")
        ids.add(jid)
        argv, err = parse_command(root, str(e.get("command", "")))
        if err:
            problems.append(f"{jid}: {err}")
            continue
        if not argv[1].startswith("code/"):
            problems.append(f"{jid}: the script must live under code/")
        if not (root / argv[1]).is_file():
            problems.append(f"{jid}: {argv[1]} does not exist")
        slots = [str(x).strip() for x in e.get("slots") or []] if isinstance(e.get("slots"), list) else []
        bad = [x for x in slots if not x or x in seen or x == "provenance"]
        if bad:
            problems.append(f"{jid}: repeated or invalid slots ({', '.join(bad[:3])})")
        if declared_slots is not None:
            unknown = [x for x in slots if x not in declared_slots]
            if unknown:
                problems.append(f"{jid}: slots not declared in paper/experimental_log.md ({', '.join(unknown[:3])})")
        seen |= set(slots)
        try:
            minutes = float(e.get("timeout_minutes", MAX_JOB_MINUTES))
        except (TypeError, ValueError):
            minutes = MAX_JOB_MINUTES
        jobs.append({"id": jid, "argv": argv, "slots": slots,
                     "timeout_s": int(max(1.0, min(minutes, MAX_JOB_MINUTES)) * 60)})
    return jobs, problems


def requirements_job(root: Path) -> dict | None:
    """Installing code/requirements.txt, as a job that must succeed before the scripts run."""
    if not (root / "code" / "requirements.txt").is_file():
        return None
    return {"id": "install", "argv": ["python", "-m", "pip", "install", "-r", "code/requirements.txt"],
            "script": "code/requirements.txt", "slots": [], "timeout_s": 15 * 60, "required": True}


def submit(store: Store, project_id: str, conversation_id: str, kind: str, root: Path, jobs: list[dict],
           log_dir: Path, out_json: Path) -> str:
    """Record a server run for approved jobs and start it. Returns the run id."""
    from .db import new_id
    rid, ts = new_id("run"), now()
    prompt = "Server run of the approved commands:\n" + "\n".join(f"- {j['id']}: {' '.join(j['argv'])}" for j in jobs)
    store.exec("INSERT INTO runs(id,project_id,conversation_id,kind,prompt,status,provider,created_at) "
               "VALUES (?,?,?,?,?,?,?,?)", (rid, project_id, conversation_id, kind, prompt, "queued", PROVIDER, ts))
    start(store, rid, root, jobs, log_dir, out_json)
    return rid


def verified_slots(out_json: Path) -> set[str] | None:
    """Slots that a recorded server run actually measured (exit 0 and a fresh, valid results file)."""
    try:
        log = json.loads(out_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {slot for j in log.get("jobs", []) if j.get("exit_code") == 0
            for slot, info in (j.get("slots") or {}).items() if info.get("ok")}
