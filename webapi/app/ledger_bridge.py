"""Bridge between the web app and the ResearchLedger evidence ledger (docs/RESEARCHLEDGER_OS_BLUEPRINT.md §5 P3).

The ledger (`researchledger/`) stays the authority on scientific state; this module only feeds it and reads it.
Each project workspace is also a ledger workspace (research/runs, research/evidence, research/claims).

- Runs: every finished server job with measured results is imported with
  `researchledger.runner.record_external_execution` as a sealed, hash-chained R#### run. Nothing is re-executed;
  the manifest says NOT_INDEPENDENTLY_REPRODUCED and carries the app's receipt (script, code, data and environment
  fingerprints) as an artifact.
- Evidence: one E### per imported job, status **observed** (recorded by a run, not yet reviewed). Only the user
  promotes it to *checked* (reviewed) or *verified* (confirmed, e.g. reproduced), through the ledger's transactional
  `apply_evidence_revision`, which also re-derives every claim's status.
- Claims: each pre-registered experiment with a verdict becomes a C### claim (its hypothesis); its run's evidence
  supports it (verdict supported) or contradicts it (not supported). The user can add claims and bind evidence.

Claim status is never set by hand or by an agent: it is derived by the ledger from evidence status.
Idempotent: links between app records and ledger ids live in the `ledger_links` table.
"""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from researchledger.atomic import atomic_write_text
from researchledger.evidence import create_evidence
from researchledger.models import Claim, Evidence, load_claims, load_evidence, recompute_claim_status
from researchledger.revision import apply_evidence_revision
from researchledger.runner import record_external_execution
from researchledger.trace import trace as ledger_trace
from researchledger.validator import list_runs, validate
from researchledger.workspace import Workspace, init_workspace, ledger_lock, next_id

from . import workspace
from .db import Store, now

USER_STATUSES = ("observed", "checked", "verified", "invalidated")
STATUS_WORDS = {
    "proposed": "proposed, no run yet", "observed": "recorded by a run, not reviewed", "checked": "reviewed by you",
    "verified": "confirmed by you (e.g. reproduced)", "contradicted": "contradicted", "invalidated": "withdrawn as invalid",
    "superseded": "replaced",
}


class LedgerError(ValueError):
    pass


def ws_for(project_id: str) -> Workspace:
    return init_workspace(workspace.project_root(project_id))


def _link(store: Store, project_id: str, kind: str, app_ref: str) -> str | None:
    r = store.one("SELECT ledger_id FROM ledger_links WHERE project_id=? AND kind=? AND app_ref=?",
                  (project_id, kind, app_ref))
    return r and r["ledger_id"]


def _set_link(store: Store, project_id: str, kind: str, app_ref: str, ledger_id: str) -> None:
    store.exec("INSERT OR REPLACE INTO ledger_links(project_id, kind, app_ref, ledger_id, created_at) VALUES (?,?,?,?,?)",
               (project_id, kind, app_ref, ledger_id, now()))


def _bind(ws: Workspace, eid: str, cid: str, relation: str) -> None:
    """Make evidence `eid` support or contradict claim `cid` (both files), then re-derive the claim's status."""
    with ledger_lock(ws):
        ev = Evidence.load(ws.evidence_dir / f"{eid}.md")
        cl = Claim.load(ws.claims_dir / f"{cid}.md")
        if relation == "supports":
            if cid not in ev.supports:
                ev.supports.append(cid)
            if eid not in cl.evidence:
                cl.evidence.append(eid)
        else:
            if cid not in ev.contradicts:
                ev.contradicts.append(cid)
            if eid not in cl.contradicts:
                cl.contradicts.append(eid)
        ev.raw_frontmatter["updated_at"] = now()
        atomic_write_text(ev.path, ev.render())
        evmap = load_evidence(ws)
        cl.status = recompute_claim_status(cl, evmap)
        cl.raw_frontmatter["updated_at"] = now()
        atomic_write_text(cl.path, cl.render())


def _new_claim(ws: Workspace, name: str, statement: str, extra: str = "") -> str:
    with ledger_lock(ws):
        cid = next_id(ws.claims_dir, "C", 3)
        body = f"# Claim: {name}\n\n## Statement\n\n{statement.strip()}\n" + (f"\n{extra.strip()}\n" if extra else "")
        claim = Claim(id=cid, path=ws.claims_dir / f"{cid}.md", schema_version="2.0", name=name[:200],
                      status="hypothesis", body=body, raw_frontmatter={"created_at": now(), "updated_at": now()})
        atomic_write_text(claim.path, claim.render())
    return cid


# ------------------------------------------------------------------ import from the execution service
def _import_job(store: Store, project_id: str, ws: Workspace, root: Path, log: dict, file_rel: str, job: dict) -> str | None:
    """One finished job with measured values -> sealed ledger run + observed evidence. Returns E### (or None)."""
    run_id = log.get("run_id") or f"legacy:{file_rel}"
    ref = f"{run_id}:{job.get('id')}"
    done = _link(store, project_id, "evidence", ref)
    if done:
        return done
    values = {k: v.get("value") for k, v in (job.get("slots") or {}).items() if v.get("ok")}
    if job.get("exit_code") != 0 or not values:
        return None
    imports = ws.research_dir / "imports"
    imports.mkdir(parents=True, exist_ok=True)
    safe = ref.replace(":", "_").replace("/", "_")
    metrics = imports / f"{safe}.metrics.json"
    atomic_write_text(metrics, json.dumps(values, indent=2))
    rc = log.get("receipt") or {}
    execution = {"exit_code": 0, "status": "PASS", "started_at": job.get("started_at"), "timeout": None,
                 "source": "ResearchLedger web execution service", "runner": log.get("runner") or "host",
                 "app_run_id": run_id, "job": job.get("id"), "script": job.get("script"),
                 "script_sha256": job.get("script_sha256"), "receipt": file_rel,
                 "code_tree_sha256": (rc.get("code") or {}).get("tree_sha256"),
                 "data_tree_sha256": (rc.get("data") or {}).get("tree_sha256"),
                 "python": (rc.get("environment") or {}).get("python"), "repeat_of": log.get("repeat_of")}
    try:
        argv = shlex.split(job.get("command") or "") or ["python"]
    except ValueError:
        argv = [job.get("command") or "python"]
    rid = _link(store, project_id, "run", ref)
    if not rid:
        manifest = record_external_execution(ws, command=argv, metrics_path=metrics,
                                             artifact_paths=[root / file_rel], execution=execution)
        rid = manifest["run_id"]
        _set_link(store, project_id, "run", ref, rid)
    label = ", ".join(f"{k} = {v}" for k, v in list(values.items())[:4])
    name = f"{job.get('id')} in {run_id}" + (f" (repeat of {log['repeat_of']})" if log.get("repeat_of") else "") + f": {label}"
    ev = create_evidence(ws, from_run=rid, status="observed", source_kind="experiment", name=name[:200])
    _set_link(store, project_id, "evidence", ref, ev.id)
    return ev.id


def _claims_from_loops(store: Store, project_id: str, ws: Workspace, root: Path, job_evidence: dict) -> int:
    """Pre-registered experiments with a verdict -> claims, bound to the evidence of the run that measured them."""
    from . import loops
    n = 0
    for st in loops.all_states(project_id):
        if st.get("type") != "experiment":
            continue
        base = root / loops.LOOPS / st["id"]
        try:
            prereg = {e["id"]: e for e in json.loads((base / "preregistration.json").read_text(encoding="utf-8"))
                      .get("experiments", [])}
        except (OSError, ValueError, KeyError, AttributeError):
            continue
        for rdir in sorted(base.glob("round_*")):
            try:
                verdicts = json.loads((rdir / "verdicts.json").read_text(encoding="utf-8"))
                runlog = json.loads((rdir / "run_log.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for eid, v in verdicts.items():
                e = prereg.get(eid)
                if not e or not isinstance(v, dict):
                    continue
                key = f"loop:{st['id']}:{eid}"
                cid = _link(store, project_id, "claim", key)
                if not cid:
                    crit = e.get("success") or {}
                    cid = _new_claim(ws, f"{eid}: {e.get('question', '')}"[:200], e.get("hypothesis", ""),
                                     f"## Pre-registered\n\nLoop `{st['id']}`; criterion: `{json.dumps(crit)}` "
                                     f"(locked in `{loops.LOOPS}/{st['id']}/preregistration.json`).")
                    _set_link(store, project_id, "claim", key, cid)
                    n += 1
                ev = job_evidence.get(f"{runlog.get('run_id')}:{eid}")
                relation = {"supported": "supports", "not_supported": "contradicts"}.get(v.get("verdict"))
                if ev and relation and not _link(store, project_id, "bind", f"{key}:{ev}"):
                    _bind(ws, ev, cid, relation)
                    _set_link(store, project_id, "bind", f"{key}:{ev}", relation)
    return n


def sync(store: Store, project_id: str) -> dict:
    """Bring the ledger up to date with recorded runs and pre-registered verdicts (idempotent)."""
    from . import lab, loops
    root = workspace.project_root(project_id)
    receipts = lab._receipts(root)
    if not receipts and not any(st.get("type") == "experiment" for st in loops.all_states(project_id)):
        return {"evidence_added": 0, "claims_added": 0}  # nothing measured yet: do not create an empty ledger
    ws = ws_for(project_id)
    added, job_evidence = 0, {}
    known = {x["id"] for x in store.all("SELECT id FROM runs WHERE project_id=?", (project_id,))}
    for r in sorted(receipts, key=lambda x: x["finished_at"] or ""):
        if r["run_id"] not in known:  # a file an agent wrote into the workspace is not a run the server executed
            continue
        try:
            log = json.loads((root / r["file"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        log.setdefault("run_id", r["run_id"])
        log.setdefault("repeat_of", r.get("repeat_of"))
        for job in log.get("jobs") or []:
            before = _link(store, project_id, "evidence", f"{log['run_id']}:{job.get('id')}")
            eid = _import_job(store, project_id, ws, root, log, r["file"], job)
            if eid:
                job_evidence[f"{log['run_id']}:{job.get('id')}"] = eid
                added += 0 if before else 1
    claims = _claims_from_loops(store, project_id, ws, root, job_evidence)
    return {"evidence_added": added, "claims_added": claims}


def safe_sync(store: Store, project_id: str) -> dict:
    try:
        return sync(store, project_id)
    except Exception as exc:  # noqa: BLE001 — the ledger import must never break a run or a loop
        store.log_activity(project_id, "ledger_sync_failed", str(exc)[:500])
        return {"error": str(exc)}


# ------------------------------------------------------------------ user actions
def add_claim(store: Store, project_id: str, statement: str, name: str = "", supports: list[str] | None = None,
              contradicts: list[str] | None = None) -> str:
    statement = (statement or "").strip()
    if len(statement) < 5:
        raise LedgerError("write the claim as one clear sentence")
    ws = ws_for(project_id)
    known = load_evidence(ws)
    for eid in (supports or []) + (contradicts or []):
        if eid not in known:
            raise LedgerError(f"no such evidence: {eid}")
    cid = _new_claim(ws, (name or statement)[:200], statement)
    for eid in supports or []:
        _bind(ws, eid, cid, "supports")
    for eid in contradicts or []:
        _bind(ws, eid, cid, "contradicts")
    store.exec("INSERT INTO audit_events(project_id, ts, actor, action, detail) VALUES (?,?,?,?,?)",
               (project_id, now(), "user", "claim_added", cid))
    return cid


def bind(store: Store, project_id: str, eid: str, cid: str, relation: str) -> None:
    if relation not in {"supports", "contradicts"}:
        raise LedgerError("relation must be supports or contradicts")
    ws = ws_for(project_id)
    if eid not in load_evidence(ws) or cid not in load_claims(ws):
        raise LedgerError("unknown evidence or claim")
    _bind(ws, eid, cid, relation)
    store.exec("INSERT INTO audit_events(project_id, ts, actor, action, detail) VALUES (?,?,?,?,?)",
               (project_id, now(), "user", "evidence_bound", f"{eid} {relation} {cid}"))


def set_status(store: Store, project_id: str, eid: str, status: str, reason: str) -> dict:
    """The user's judgment on one piece of evidence. Claim statuses follow automatically (ledger rules)."""
    if status not in USER_STATUSES:
        raise LedgerError(f"status must be one of {', '.join(USER_STATUSES)}")
    if not (reason or "").strip():
        raise LedgerError("say briefly why (it is kept with the change)")
    try:
        out = apply_evidence_revision(ws_for(project_id), {eid: status}, reason=reason.strip()[:1000])
    except Exception as exc:  # noqa: BLE001 — ledger refusals (unknown id, conflicts, invalid workspace) are user errors
        msg = str(exc)
        m = re.search(r"RL120: (C\d+)", msg)
        if m:
            raise LedgerError(f"{eid} is the only support of claim {m.group(1)}. Withdraw that claim first (or add "
                              f"other evidence for it), then mark {eid} as {status}.") from exc
        raise LedgerError(msg) from exc
    store.exec("INSERT INTO audit_events(project_id, ts, actor, action, detail) VALUES (?,?,?,?,?)",
               (project_id, now(), "user", "evidence_status", f"{eid} -> {status}: {reason[:300]}"))
    return out


def withdraw_claim(store: Store, project_id: str, cid: str, reason: str) -> None:
    """The user withdraws a claim. It stays in the ledger, marked withdrawn, with the reason in its body."""
    if not (reason or "").strip():
        raise LedgerError("say briefly why the claim is withdrawn")
    ws = ws_for(project_id)
    with ledger_lock(ws):
        path = ws.claims_dir / f"{cid}.md"
        if not path.is_file():
            raise LedgerError(f"no such claim: {cid}")
        cl = Claim.load(path)
        cl.status = "withdrawn"
        cl.body = cl.body.rstrip() + f"\n\n## Withdrawn\n\n{reason.strip()[:1000]} ({now()[:10]})\n"
        cl.raw_frontmatter["updated_at"] = now()
        atomic_write_text(path, cl.render())
    store.exec("INSERT INTO audit_events(project_id, ts, actor, action, detail) VALUES (?,?,?,?,?)",
               (project_id, now(), "user", "claim_withdrawn", f"{cid}: {reason[:300]}"))


def overview(store: Store, project_id: str) -> dict:
    ws = ws_for(project_id)
    evidence, claims, runs = load_evidence(ws), load_claims(ws), list_runs(ws)
    app = {r["ledger_id"]: r["app_ref"] for r in store.all(
        "SELECT ledger_id, app_ref FROM ledger_links WHERE project_id=? AND kind IN ('run','evidence')", (project_id,))}

    def values(e: Evidence) -> dict:
        for rid in e.runs:
            m = runs.get(rid) or {}
            p = ws.runs_dir / rid / (m.get("metrics") or "metrics.json")
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
        return {}
    res = validate(ws)
    from . import lab
    try:
        repro = lab.reproducibility(project_id)
    except Exception:  # noqa: BLE001 — a label must never stop the evidence page from loading
        repro = {}

    def repeatability(ref: str | None) -> dict | None:
        r = repro.get((ref or "").split(":")[0])
        return {"level": r["level"], "label": r["label"], "meaning": r["meaning"]} if r else None
    return {
        "claims": [{"id": c.id, "name": c.name, "status": c.status, "statement": c.statement(),
                    "evidence": c.evidence, "contradicts": c.contradicts} for c in sorted(claims.values(), key=lambda c: c.id)],
        "evidence": [{"id": e.id, "name": e.name, "status": e.status, "meaning": STATUS_WORDS.get(e.status, e.status),
                      "supports": e.supports, "contradicts": e.contradicts, "runs": e.runs, "values": values(e),
                      "app_ref": app.get(e.id), "repeatability": repeatability(app.get(e.id))}
                     for e in sorted(evidence.values(), key=lambda e: e.id)],
        "runs": [{"id": rid, "command": m.get("command"), "finished_at": m.get("finished_at"),
                  "reproducibility": m.get("reproducibility_status") or ("replayable" if m.get("replay_supported") else None),
                  "app_ref": app.get(rid)} for rid, m in sorted(runs.items())],
        "issues": [{"level": i.level, "code": i.code, "message": i.message} for i in res.issues],
        "valid": not res.errors,
        "status_words": STATUS_WORDS,
    }


def trace(project_id: str, entity_id: str) -> str:
    try:
        return ledger_trace(ws_for(project_id), entity_id)
    except Exception as exc:  # noqa: BLE001
        raise LedgerError(str(exc)) from exc
