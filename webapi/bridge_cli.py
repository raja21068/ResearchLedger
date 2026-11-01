"""Worker helper for the Claude app bridge (standard library only, runs with any Python 3.8+).

Used by the `/rl-worker` command inside a Claude Code session in the Claude app:

    python webapi/bridge_cli.py next [--wait 540]     claim a task (long-poll); prints JSON or NO_TASK
    python webapi/bridge_cli.py say  RUN_ID "text"    show a progress message in the website chat
    python webapi/bridge_cli.py step RUN_ID "text"    show a step ("Searched …", "Wrote …")
    python webapi/bridge_cli.py todos RUN_ID "- [x] done\\n- > doing\\n- todo"
    python webapi/bridge_cli.py done RUN_ID --summary-file reply.md [--failed]
    python webapi/bridge_cli.py done RUN_ID --summary "short reply"
"""
import argparse
import json
import os
import sys
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


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="bridge_cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next"); n.add_argument("--wait", type=int, default=540)
    for k in ("say", "step", "todos"):
        s = sub.add_parser(k); s.add_argument("run_id"); s.add_argument("text")
    d = sub.add_parser("done"); d.add_argument("run_id")
    d.add_argument("--summary", default=""); d.add_argument("--summary-file"); d.add_argument("--failed", action="store_true")
    a = p.parse_args()

    if a.cmd == "next":
        end = time.time() + a.wait
        while True:
            code, body = call("POST", "/bridge/next")
            if code == 200 and body:
                print(json.dumps(body, indent=2, ensure_ascii=False))
                return
            if time.time() >= end:
                print("NO_TASK")
                return
            time.sleep(3)
    elif a.cmd in ("say", "step", "todos"):
        kind = {"say": "say", "step": "step", "todos": "todos"}[a.cmd]
        code, body = call("POST", f"/bridge/runs/{a.run_id}/event", {"kind": kind, "text": a.text})
        print("ok" if code == 200 else f"error {code}: {body}")
    else:
        summary = a.summary
        if a.summary_file:
            with open(a.summary_file, encoding="utf-8") as f:
                summary = f.read()
        code, body = call("POST", f"/bridge/runs/{a.run_id}/done", {"summary": summary, "failed": a.failed})
        print(f"done: {body.get('status')}" if code == 200 and isinstance(body, dict) else f"error {code}: {body}")


if __name__ == "__main__":
    main()
