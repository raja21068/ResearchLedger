"""ResearchLedger from the Claude console (standard library only). Used by the /rl and /rl-status commands.

    python webapi/rl_cli.py step PROJECT STEP [--text "..."] [--files F ...] [--option name=value]
                                                                    start step 1-7 (literature, idea, code, experiments,
                                                                    write, review, check) exactly like the website
    python webapi/rl_cli.py menu                                    the numbered research steps (same as the GUI)
    python webapi/rl_cli.py status                                  worker, decisions, what is running
    python webapi/rl_cli.py list                                    your papers and recent quick jobs (with ids)
    python webapi/rl_cli.py new "title" [--paper]                   create a quick job (or a paper); prints its id
    python webapi/rl_cli.py add PROJECT PATH [PATH ...]             upload files; a .zip is unpacked safely
    python webapi/rl_cli.py tool "goal" [--files F ...] [--repeat review|idea]   which tool would run (starts nothing)
    python webapi/rl_cli.py start PROJECT "goal" [--files F ...] [--repeat review|idea]
    python webapi/rl_cli.py experiment PROJECT "what to run" [--from LOOP] [--tex PAPER.tex]
    python webapi/rl_cli.py loop PROJECT LOOP [show|continue|stop|accept|retry]
    python webapi/rl_cli.py decisions                               everything waiting for the user
    python webapi/rl_cli.py approve PROJECT STAGE                   approve a paper stage
    python webapi/rl_cli.py check PROJECT TEX                       submission check of a .tex
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

API = os.environ.get("RL_API_URL", "http://127.0.0.1:8000").rstrip("/") + "/api/v1"
WEB = os.environ.get("RL_WEB_URL", "http://localhost:3000").rstrip("/")
MAX_ZIP_FILES, MAX_ZIP_BYTES = 400, 300 * 1024 * 1024
SKIP = {"__MACOSX", ".git", "node_modules", "__pycache__", ".DS_Store"}


def call(method, path, body=None, raw=None, ctype="application/json", timeout=60):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"content-type": ctype, "x-rl-client": "console"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = r.read()
            return json.loads(out) if out else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("detail", detail)
        except ValueError:
            pass
        sys.exit(f"PROBLEM: {detail}")
    except urllib.error.URLError as e:
        sys.exit("API_DOWN: ResearchLedger is not running. Start it with: "
                 r"& D:\AutoResearch\ResearchLedger\start_web.ps1")


def upload(project, path: Path, folder="uploads"):
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    q = urllib.parse.urlencode({"folder": folder})
    return call("POST", f"/projects/{project}/files?{q}", raw=body, ctype=f"multipart/form-data; boundary={boundary}",
                timeout=300)["path"]


def unzip_safely(zpath: Path, dest: Path) -> list[Path]:
    """Extract only regular files with relative, non-escaping names; refuse oversized archives."""
    out, total = [], 0
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p]
            if info.is_dir() or not parts or name.startswith("/") or ".." in parts or ":" in parts[0] \
                    or any(p in SKIP for p in parts) or (info.external_attr >> 16) & 0o170000 == 0o120000:
                continue
            total += info.file_size
            if len(out) >= MAX_ZIP_FILES or total > MAX_ZIP_BYTES:
                sys.exit(f"ERROR: {zpath.name} is too large (limit {MAX_ZIP_FILES} files / 300 MB)")
            target = dest.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            out.append(target)
    return out


def show(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main():
    for s in (sys.stdout, sys.stderr):  # Windows consoles default to a legacy code page
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="ResearchLedger from the Claude console")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("menu")
    p = sub.add_parser("step"); p.add_argument("project"); p.add_argument("step")
    p.add_argument("--text", default=""); p.add_argument("--text-file")
    p.add_argument("--files", nargs="*", default=[]); p.add_argument("--option", action="append", default=[])
    sub.add_parser("status")
    sub.add_parser("list")
    sub.add_parser("decisions")
    p = sub.add_parser("new"); p.add_argument("title"); p.add_argument("--paper", action="store_true")
    p = sub.add_parser("add"); p.add_argument("project"); p.add_argument("paths", nargs="+")
    for name in ("tool", "start"):
        p = sub.add_parser(name)
        if name == "start":
            p.add_argument("project")
        p.add_argument("goal"); p.add_argument("--files", nargs="*", default=[])
        p.add_argument("--repeat", choices=["review", "idea"])
    p = sub.add_parser("experiment"); p.add_argument("project"); p.add_argument("text")
    p.add_argument("--from", dest="from_loop"); p.add_argument("--tex")
    p = sub.add_parser("loop"); p.add_argument("project"); p.add_argument("loop")
    p.add_argument("action", nargs="?", default="show", choices=["show", "continue", "stop", "accept", "retry"])
    p = sub.add_parser("approve"); p.add_argument("project"); p.add_argument("stage")
    p = sub.add_parser("check"); p.add_argument("project"); p.add_argument("tex")
    a = ap.parse_args()

    if a.cmd == "step":
        text = Path(a.text_file).read_text(encoding="utf-8") if a.text_file else a.text
        opts = dict(o.split("=", 1) for o in a.option if "=" in o)
        r = call("POST", f"/projects/{a.project}/steps/{a.step}/start", {"text": text, "files": a.files, "options": opts})
        print(f"Started: {r['label']}")
        print(f"Open: {WEB}{r['url']}")
    elif a.cmd == "menu":
        print(call("GET", "/steps")["menu"])
    elif a.cmd == "status":
        b = call("GET", "/bridge/status")
        inbox = call("GET", "/inbox")
        print(f"Worker: {b['worker_state']} (executor {b['executor']}), tasks waiting for it: {b['queued']}")
        print(f"Decisions waiting: {inbox['counts']['approve']} to approve, {inbox['counts']['retry']} to retry; "
              f"working now: {inbox['counts']['running']}")
        for r in inbox["running"][:10]:
            print(f"  working: {r.get('project')} · {r.get('stage')}")
    elif a.cmd == "list":
        for p in call("GET", "/projects?kind=paper"):
            print(f"PAPER  {p['id']}  {p['title']}")
        for p in call("GET", "/projects?kind=quick")[:15]:
            print(f"QUICK  {p['id']}  {p['title']}")
    elif a.cmd == "decisions":
        inbox = call("GET", "/inbox")
        for x in inbox["approve"] + inbox["retry"]:
            where = (f"loop {x['loop_id']}" if x.get("loop_id") else f"stage {x['stage_id']}" if x.get("stage_id")
                     else f"chat {x.get('conversation_id')}")
            print(f"- [{x['project_id']}] {x.get('project')} · {x.get('stage')} · {where}\n    "
                  + str(x.get("summary") or x.get("error") or "")[:300].replace("\n", " "))
        if not inbox["approve"] and not inbox["retry"]:
            print("Nothing needs you right now.")
    elif a.cmd == "new":
        p = call("POST", "/projects", {"title": a.title[:200], "kind": "paper" if a.paper else "quick"})
        print(p["id"])
    elif a.cmd == "add":
        for raw in a.paths:
            path = Path(raw.strip('"'))
            if not path.is_file():
                sys.exit(f"ERROR: file not found: {path}")
            if path.suffix.lower() == ".zip":
                with tempfile.TemporaryDirectory() as tmp:
                    files = unzip_safely(path, Path(tmp))
                    for f in files:
                        rel = f.relative_to(tmp).parent.as_posix()
                        folder = f"uploads/{path.stem}" + (f"/{rel}" if rel != "." else "")
                        print(upload(a.project, f, folder))
                    print(f"# unpacked {len(files)} files from {path.name}", file=sys.stderr)
            else:
                print(upload(a.project, path))
    elif a.cmd == "tool":
        d = call("POST", "/autopilot/classify", {"goal": a.goal, "filenames": [Path(f).name for f in a.files],
                                                 "repeat": a.repeat})
        print(f"Tool: {d.get('tool') or '(none)'}\nWhy: {d.get('why')}")
    elif a.cmd == "start":
        r = call("POST", f"/projects/{a.project}/autopilot/start", {"goal": a.goal, "files": a.files, "repeat": a.repeat})
        show({k: r.get(k) for k in ("mode", "loop", "recipe", "paper_type", "why", "loop_id", "missing") if r.get(k)}
             | {"open": WEB + r["url"]})
    elif a.cmd == "experiment":
        r = call("POST", f"/projects/{a.project}/loops", {"type": "experiment", "experiments_text": a.text,
                                                          "from_loop": a.from_loop, "manuscript": a.tex})
        print(f"loop {r['id']} started · {WEB}/projects/{a.project}/loops/{r['id']}")
    elif a.cmd == "loop":
        if a.action == "show":
            v = call("GET", f"/projects/{a.project}/loops/{a.loop}")
        else:
            v = call("POST", f"/projects/{a.project}/loops/{a.loop}/{a.action}")
        last = v["rounds"][-1] if v.get("rounds") else {}
        show({"loop": v["id"], "type": v["label"], "status": v["status"], "round": v.get("round"), "move": v.get("move"),
              "waiting_for_you": v.get("paused_reason"), "stop_reason": v.get("stop_reason"),
              "last_round_metrics": {k: last.get("metrics", {}).get(k) for k in ("total", "verified_major", "mean_score")
                                     if last.get("metrics", {}).get(k) is not None},
              "final_files": v.get("final_files"), "open": f"{WEB}/projects/{a.project}/loops/{a.loop}"})
    elif a.cmd == "approve":
        call("POST", f"/projects/{a.project}/paper/stages/{a.stage}/approve")
        print(f"approved {a.stage}")
    elif a.cmd == "check":
        r = call("POST", f"/projects/{a.project}/quality", {"tex": a.tex, "target_refs": 40}, timeout=300)
        print(("READY: no failing check" if r["ready"] else f"NOT READY: {r['counts']['fail']} failing check(s)")
              + f", {r['counts']['warn']} warning(s)")
        for c in r["checks"]:
            if c["status"] in {"fail", "warn"}:
                print(f"  {c['status'].upper():4} {c['label']}: {c['detail']}")


if __name__ == "__main__":
    main()
