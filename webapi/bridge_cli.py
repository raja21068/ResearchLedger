"""Worker helper for the Claude app bridge (standard library only, runs with any Python 3.8+).

Used by the `/rl-worker` command inside a Claude Code session in the Claude app:

    python webapi/bridge_cli.py next [--wait 540]     claim a task (long-poll); prints JSON or NO_TASK
    python webapi/bridge_cli.py say  RUN_ID "text"    show a progress message in the website chat
    python webapi/bridge_cli.py step RUN_ID "text"    show a step ("Searched …", "Wrote …")
    python webapi/bridge_cli.py todos RUN_ID "- [x] done\\n- > doing\\n- todo"
    python webapi/bridge_cli.py ping RUN_ID           "still working" (sent automatically every 2 minutes after `next`)
    python webapi/bridge_cli.py done RUN_ID --summary-file reply.md [--failed]
    python webapi/bridge_cli.py done RUN_ID --summary "short reply"
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

API = os.environ.get("RL_API_URL", "http://127.0.0.1:8000").rstrip("/") + "/api/v1"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"content-type": "application/json", "x-rl-client": "bridge"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except urllib.error.URLError as e:
        sys.exit(f"Cannot reach the ResearchLedger API at {API}: {e.reason}. Is the backend running?")


CLAIMS = os.path.join(tempfile.gettempdir(), "rl_bridge_claims.json")


def _remember_claim(run_id, token):
    """The server hands out a claim token per task; keep it so later commands send it automatically."""
    try:
        with open(CLAIMS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data[run_id] = token
    data = dict(list(data.items())[-20:])
    with open(CLAIMS, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _claim_for(run_id):
    try:
        with open(CLAIMS, encoding="utf-8") as f:
            return json.load(f).get(run_id)
    except (OSError, ValueError):
        return None


HEARTBEAT_S = 120            # a claimed task pings the server this often while it is open
MAX_HEARTBEAT_S = 2 * 3600   # a worker that crashed still releases its task within this long


def _start_heartbeat(run_id):
    """A small detached process that keeps a claimed task alive during long steps (installs, long scripts).
    It stops by itself when the server no longer considers the task running, or after MAX_HEARTBEAT_S."""
    if os.environ.get("RL_NO_HEARTBEAT") == "1":
        return
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    try:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "_heartbeat", run_id], **kw)
    except OSError:
        pass  # without it the worker can still ping by hand


def _heartbeat(run_id):
    end = time.time() + MAX_HEARTBEAT_S
    while time.time() < end:
        time.sleep(HEARTBEAT_S)
        try:
            code, _ = call("POST", f"/bridge/runs/{run_id}/event",
                           {"kind": "ping", "text": "heartbeat", "claim": _claim_for(run_id)})
        except SystemExit:  # server down: try again next time
            continue
        if code != 200:
            return  # finished, cancelled or re-queued


def _error(code, body):
    if code == 409:
        return (f"STOP: {body} The task went back to the queue. Discard your work on it and run `next` again.")
    return f"error {code}: {body}"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="bridge_cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next"); n.add_argument("--wait", type=int, default=540)
    for k in ("say", "step", "todos"):
        s = sub.add_parser(k); s.add_argument("run_id"); s.add_argument("text")
    sub.add_parser("ping").add_argument("run_id")
    sub.add_parser("_heartbeat").add_argument("run_id")
    d = sub.add_parser("done"); d.add_argument("run_id")
    d.add_argument("--summary", default=""); d.add_argument("--summary-file"); d.add_argument("--failed", action="store_true")
    a = p.parse_args()

    if a.cmd == "next":
        end = time.time() + a.wait
        while True:
            code, body = call("POST", "/bridge/next")
            if code == 200 and body:
                _remember_claim(body["run_id"], body.get("claim"))
                _start_heartbeat(body["run_id"])
                print(json.dumps(body, indent=2, ensure_ascii=False))
                return
            if time.time() >= end:
                print("NO_TASK")
                return
            time.sleep(3)
    elif a.cmd == "_heartbeat":
        _heartbeat(a.run_id)
    elif a.cmd in ("say", "step", "todos", "ping"):
        code, body = call("POST", f"/bridge/runs/{a.run_id}/event",
                          {"kind": a.cmd, "text": getattr(a, "text", "ping"), "claim": _claim_for(a.run_id)})
        print("ok" if code == 200 else _error(code, body))
    else:
        summary = a.summary
        if a.summary_file:
            with open(a.summary_file, encoding="utf-8") as f:
                summary = f.read()
        code, body = call("POST", f"/bridge/runs/{a.run_id}/done",
                          {"summary": summary, "failed": a.failed, "claim": _claim_for(a.run_id)})
        print(f"done: {body.get('status')}" if code == 200 and isinstance(body, dict) else _error(code, body))


if __name__ == "__main__":
    main()
