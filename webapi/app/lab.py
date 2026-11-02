"""Experiment laboratory (docs/RESEARCHLEDGER_OS_BLUEPRINT.md §5 P2).

Read-mostly view over what the execution service (exprun.py) records:
- experiments: experiment loops and Paper Studio's Run experiments stage, linked to the loop they came from
  (`parent`), so they form a tree (after OpenResearch's experiment lineage);
- runs: one permanent receipt per run in results/receipts/<run_id>.json (code, data and environment fingerprints,
  commands, exit codes, logs, measured slots); run logs written before receipts existed are shown as "legacy";
- compare: slot values, code/data fingerprints and package versions of two runs side by side;
- repeat: re-run a run's exact commands as a NEW run; the project's results files are put back afterwards, so a
  repeat checks reproducibility without changing anything.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import exprun, loops, paper_studio, workspace
from .db import Store


class LabError(ValueError):
    pass


def _read(p: Path) -> dict | None:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def _summary(log: dict, path: str, legacy: bool) -> dict:
    jobs = log.get("jobs") or []
    rc = log.get("receipt") or {}
    slots = {k: v.get("value") for j in jobs for k, v in (j.get("slots") or {}).items() if v.get("ok")}
    return {"run_id": log.get("run_id"), "experiment": log.get("experiment"), "repeat_of": log.get("repeat_of"),
            "finished_at": log.get("finished_at"), "file": path, "legacy": legacy, "runner": log.get("runner"),
            "jobs": [{"id": j.get("id"), "command": j.get("command"), "exit_code": j.get("exit_code"),
                      "seconds": j.get("seconds"), "ok": j.get("ok")} for j in jobs],
            "ok": bool(jobs) and all(j.get("ok") for j in jobs), "values": slots,
            "code_sha256": (rc.get("code") or {}).get("tree_sha256"),
            "data_sha256": (rc.get("data") or {}).get("tree_sha256"),
            "python": (rc.get("environment") or {}).get("python")}


def _receipts(root: Path) -> list[dict]:
    """Every recorded run in the project, newest first: receipts, plus run logs from before receipts existed."""
    out, seen = [], set()
    rdir = root / exprun.RECEIPTS
    for p in sorted(rdir.glob("run_*.json")) if rdir.is_dir() else []:
        log = _read(p)
        if log and log.get("run_id"):
            seen.add(log["run_id"])
            out.append(_summary(log, p.relative_to(root).as_posix(), False))
    legacy = list((root / loops.LOOPS).glob("lop_*/round_*/run_log.json")) + [root / "results" / "run_log.json"]
    for p in legacy:
        log = _read(p) if p.is_file() else None
        if not log or log.get("run_id") in seen:
            continue
        if not log.get("experiment"):
            log["experiment"] = p.parts[-3] if p.parent.name.startswith("round_") else "paper"
        s = _summary(log, p.relative_to(root).as_posix(), True)
        if not s["run_id"]:
            s["run_id"] = f"legacy:{s['file']}"
        seen.add(s["run_id"])
        out.append(s)
    return sorted(out, key=lambda r: r["finished_at"] or "", reverse=True)


def tree(store: Store, project_id: str) -> dict:
    root = workspace.project_root(project_id)
    runs = _receipts(root)
    nodes = []
    states = {st["id"]: st for st in loops.all_states(project_id)}
    for st in states.values():
        if st["type"] != "experiment":
            continue
        parent = st.get("parent") or (st.get("inputs") or {}).get("from_loop")
        nodes.append({"id": st["id"], "kind": "loop", "title": (st.get("goal") or st["id"])[:160],
                      "status": st.get("status"), "parent": parent, "created_at": st.get("created_at"),
                      "verdicts": _verdicts(root, st["id"])})
        if parent and parent in states and not any(n["id"] == parent for n in nodes):
            ps = states[parent]
            nodes.append({"id": parent, "kind": "source", "title": (ps.get("goal") or parent)[:160],
                          "status": ps.get("status"), "parent": None, "created_at": ps.get("created_at"),
                          "label": loops.TYPES.get(ps["type"], {}).get("label", ps["type"])})
    if paper_studio.load(project_id) and (any(r["experiment"] == "paper" for r in runs) or (root / "code" / "jobs.json").is_file()):
        nodes.append({"id": "paper", "kind": "paper", "title": "Paper: Run experiments", "status": None,
                      "parent": None, "created_at": None})
    active = store.all("SELECT id, kind, status, created_at FROM runs WHERE project_id=? AND provider=? AND "
                       "status IN ('queued','running') ORDER BY created_at DESC", (project_id, exprun.PROVIDER))
    repro = reproducibility(project_id, runs)
    for r in runs:
        r["reproducibility"] = repro.get(r["run_id"]) or ({"level": None, "label": "a repeat", "meaning":
                                                          f"Repeat of {r['repeat_of']}; see that run's level."} if r.get("repeat_of") else None)
    return {"experiments": nodes, "runs": runs, "active": active}


def _verdicts(root: Path, loop_id: str) -> dict:
    out = {}
    for p in sorted((root / loops.LOOPS / loop_id).glob("round_*/verdicts.json")):
        v = _read(p) or {}
        out.update({k: x.get("verdict") for k, x in v.items() if isinstance(x, dict)})
    return out


def receipt(project_id: str, run_id: str) -> dict:
    root = workspace.project_root(project_id)
    for r in _receipts(root):
        if r["run_id"] == run_id:
            log = _read(root / r["file"]) or {}
            return {**log, "file": r["file"], "legacy": r["legacy"]}
    raise LabError("run not found")


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None


def compare(project_id: str, a: str, b: str) -> dict:
    ra, rb = receipt(project_id, a), receipt(project_id, b)
    va = {k: v.get("value") for j in ra.get("jobs", []) for k, v in (j.get("slots") or {}).items() if v.get("ok")}
    vb = {k: v.get("value") for j in rb.get("jobs", []) for k, v in (j.get("slots") or {}).items() if v.get("ok")}
    slots = []
    for k in sorted(set(va) | set(vb)):
        x, y = va.get(k), vb.get(k)
        d = {"slot": k, "a": x, "b": y, "same": x == y}
        if _num(x) is not None and _num(y) is not None:
            d["diff"] = y - x
            d["rel_diff"] = (y - x) / abs(x) if x else None
        slots.append(d)
    fa, fb = ra.get("receipt") or {}, rb.get("receipt") or {}

    def files(rc, part):
        return {f["path"]: f["sha256"] for f in (rc.get(part) or {}).get("files", [])}
    changed = {part: sorted(p for p in set(files(fa, part)) | set(files(fb, part))
                            if files(fa, part).get(p) != files(fb, part).get(p)) for part in ("code", "data")}
    ea, eb = fa.get("environment") or {}, fb.get("environment") or {}
    pk = sorted(set(ea.get("packages") or {}) | set(eb.get("packages") or {}))
    return {"a": a, "b": b, "slots": slots,
            "same_values": bool(slots) and all(s["same"] for s in slots),
            "code_same": (fa.get("code") or {}).get("tree_sha256") == (fb.get("code") or {}).get("tree_sha256")
            if fa and fb else None,
            "data_same": (fa.get("data") or {}).get("tree_sha256") == (fb.get("data") or {}).get("tree_sha256")
            if fa and fb else None,
            "changed_files": changed,
            "environment": {"python": [ea.get("python"), eb.get("python")],
                            "packages": [{"name": n, "a": (ea.get("packages") or {}).get(n), "b": (eb.get("packages") or {}).get(n)}
                                         for n in pk if (ea.get("packages") or {}).get(n) != (eb.get("packages") or {}).get(n)]},
            "fingerprints_missing": not (fa and fb)}


LEVELS = {
    0: ("not usable", "The run did not finish cleanly, or has no recorded results."),
    1: ("run once", "One sealed run. Nothing has checked that it can be repeated."),
    2: ("repeated here", "Run again with the same code, data and environment and the same values came out."),
    3: ("repeated elsewhere", "Run again in a different environment (other Python or package versions) with the same values."),
}
NOT_REPRODUCED = ("not reproduced", "A repeat with the same code and data gave different values. Treat the result as unstable.")
INDEPENDENT = "Independent replication (a different team or code) is never decided by the software; record it yourself."


def _env_key(rc: dict) -> str:
    e = (rc.get("receipt") or {}).get("environment") or {}
    return json.dumps({"python": e.get("python"), "packages": e.get("packages") or {}}, sort_keys=True)


def reproducibility(project_id: str, runs: list[dict] | None = None) -> dict:
    """Reproducibility level of every original run, from the repeats recorded in the project (nothing is assumed).

    1 run once; 2 repeated with the same code, data and environment and the same values; 3 the same values in a
    different environment. A repeat that gave different values with the same code and data is reported as
    'not reproduced'. The fourth level, independent replication, is not computed."""
    runs = runs if runs is not None else _receipts(workspace.project_root(project_id))
    by_id = {r["run_id"]: r for r in runs}
    out = {}
    for r in runs:
        if r.get("repeat_of"):
            continue
        level, label = (1, LEVELS[1]) if r["ok"] and r["values"] else (0, LEVELS[0])
        detail = {"repeats": [], "independent_replication": INDEPENDENT}
        if level:
            for rep in (x for x in runs if x.get("repeat_of") == r["run_id"] and x["ok"]):
                try:
                    cmp = compare(project_id, r["run_id"], rep["run_id"])
                except LabError:
                    continue
                if cmp["fingerprints_missing"] or not cmp["code_same"] or not cmp["data_same"]:
                    detail["repeats"].append({"run_id": rep["run_id"], "result": "not comparable (code, data or fingerprints differ)"})
                    continue
                same_env = _env_key(receipt(project_id, r["run_id"])) == _env_key(receipt(project_id, rep["run_id"]))
                if cmp["same_values"]:
                    got = 2 if same_env else 3
                    detail["repeats"].append({"run_id": rep["run_id"], "result": "same values", "same_environment": same_env})
                    level = max(level, got)
                else:
                    detail["repeats"].append({"run_id": rep["run_id"], "result": "different values"})
                    detail["not_reproduced"] = True
        if detail.get("not_reproduced") and not any(x["result"] == "same values" for x in detail["repeats"]):
            out[r["run_id"]] = {"level": 1, "label": NOT_REPRODUCED[0], "meaning": NOT_REPRODUCED[1], **detail}
        else:
            lab_, why = LEVELS[level]
            out[r["run_id"]] = {"level": level, "label": lab_, "meaning": why, **detail}
    return out


def repeat(store: Store, project_id: str, run_id: str) -> str:
    """Run the same commands again as a new, separately recorded run (the user approved it)."""
    if store.one("SELECT id FROM runs WHERE project_id=? AND provider=? AND status IN ('queued','running')",
                 (project_id, exprun.PROVIDER)):
        raise LabError("an experiment run is already in progress in this project; repeat it when that one has finished")
    root = workspace.project_root(project_id)
    rc = receipt(project_id, run_id)
    jobs = []
    for j in rc.get("jobs") or []:
        if j.get("id") == "install":
            continue  # a repeat uses the environment as it is now, and records it
        argv, err = exprun.parse_command(root, j.get("command") or "")
        if err:
            raise LabError(f"{j.get('id')}: {err}")
        if not (root / argv[1]).is_file():
            raise LabError(f"{j.get('id')}: {argv[1]} no longer exists, so this run cannot be repeated")
        jobs.append({"id": j["id"], "argv": argv, "slots": list((j.get("slots") or {}).keys()),
                     "timeout_s": exprun.MAX_JOB_MINUTES * 60})
    if not jobs:
        raise LabError("this run has no commands that can be repeated")
    orig = store.one("SELECT conversation_id FROM runs WHERE id=?", (run_id,))
    conv = orig and orig["conversation_id"]
    if not conv:
        c = store.one("SELECT id FROM conversations WHERE project_id=? ORDER BY created_at LIMIT 1", (project_id,))
        if not c:
            raise LabError("this project has no conversation to attach the run to")
        conv = c["id"]
    return exprun.submit(store, project_id, conv, "repeat", root, jobs, None, None,
                         meta={"experiment": rc.get("experiment"), "repeat_of": run_id}, keep_results=True)
