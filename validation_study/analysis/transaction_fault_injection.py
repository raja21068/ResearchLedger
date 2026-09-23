#!/usr/bin/env python3
"""Fault-injection checks for ResearchLedger's multi-file revision transaction."""
from __future__ import annotations

import hashlib
import json
import tempfile
import os
import subprocess
import sys
from pathlib import Path

from researchledger.models import Claim, Evidence, Claim as ClaimModel, Evidence as EvidenceModel
import researchledger.revision as rev
from researchledger.revision import apply_evidence_revision, recover_incomplete_revisions
from researchledger.workspace import init_workspace

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "transaction_fault_injection.json"


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ev(ws, eid, status="verified", supports=None):
    obj = Evidence(id=eid, path=ws.evidence_dir/f"{eid}.md", schema_version="2.0", name=eid,
                   status=status, source_kind="observation", supports=supports or [], body=f"# {eid}\n")
    obj.path.write_text(obj.render(), encoding="utf-8")
    return obj


def cl(ws, cid, *, evidence, support_sets=None, status="supported"):
    obj = Claim(id=cid, path=ws.claims_dir/f"{cid}.md", schema_version="2.0", name=cid,
                status=status, evidence=evidence, support_sets=support_sets or [], body=f"## Statement\n{cid}\n")
    obj.path.write_text(obj.render(), encoding="utf-8")
    return obj


def normal_commit() -> dict:
    with tempfile.TemporaryDirectory() as td:
        ws=init_workspace(Path(td)); ev(ws,"E001",supports=["C001"]); cl(ws,"C001",evidence=["E001"])
        res=apply_evidence_revision(ws,{"E001":"superseded"},reason="fault benchmark normal commit")
        manifest=json.loads((ws.root/".researchledger"/"revisions"/res["txid"] / "manifest.json").read_text())
        return {
            "passed": EvidenceModel.load(ws.evidence_dir/"E001.md").status=="superseded"
                      and ClaimModel.load(ws.claims_dir/"C001.md").status=="hypothesis"
                      and manifest["phase"]=="committed",
            "phase": manifest["phase"],
            "files": manifest["files"],
        }


def mid_write_failure_rolls_back() -> dict:
    with tempfile.TemporaryDirectory() as td:
        ws=init_workspace(Path(td)); ev(ws,"E001",supports=["C001"]); cl(ws,"C001",evidence=["E001"])
        ep=ws.evidence_dir/"E001.md"; cp=ws.claims_dir/"C001.md"
        before={str(ep):digest(ep),str(cp):digest(cp)}
        original=rev.atomic_write_text
        state={"changed_writes":0,"raised":False}
        def flaky(path, text):
            # Only inject while applying research entity files; allow manifest/recovery writes.
            if "research" in Path(path).parts and not state["raised"]:
                state["changed_writes"] += 1
                if state["changed_writes"] == 2:
                    state["raised"] = True
                    raise OSError("injected second-entity write failure")
            return original(path,text)
        rev.atomic_write_text=flaky
        error=None
        try:
            apply_evidence_revision(ws,{"E001":"superseded"},reason="injected failure")
        except Exception as exc:
            error=f"{type(exc).__name__}: {exc}"
        finally:
            rev.atomic_write_text=original
        after={str(ep):digest(ep),str(cp):digest(cp)}
        manifests=list((ws.root/".researchledger"/"revisions").glob("*/manifest.json"))
        phase=json.loads(manifests[0].read_text())["phase"] if manifests else None
        return {
            "passed": before==after and phase=="rolled_back" and state["raised"],
            "error": error,
            "preimage_hashes_restored": before==after,
            "manifest_phase": phase,
        }


def crash_recovery_restores() -> dict:
    with tempfile.TemporaryDirectory() as td:
        ws=init_workspace(Path(td)); ev(ws,"E001")
        target=ws.evidence_dir/"E001.md"; before=target.read_text(); before_hash=digest(target)
        tx=ws.root/".researchledger"/"revisions"/"REV-crash-fixture"
        backup=tx/"before"/"research"/"evidence"/"E001.md"; backup.parent.mkdir(parents=True)
        backup.write_text(before)
        target.write_text(before.replace("status: verified","status: superseded"))
        (tx/"manifest.json").write_text(json.dumps({"phase":"applying","files":["research/evidence/E001.md"]}))
        recovered=recover_incomplete_revisions(ws)
        m=json.loads((tx/"manifest.json").read_text())
        return {
            "passed": recovered==["REV-crash-fixture"] and digest(target)==before_hash and m["phase"]=="rolled_back",
            "recovered": recovered,
            "preimage_hash_restored": digest(target)==before_hash,
            "manifest_phase": m["phase"],
        }


def alternative_support_selectivity() -> dict:
    with tempfile.TemporaryDirectory() as td:
        ws=init_workspace(Path(td))
        ev(ws,"E001",supports=["C001"]); ev(ws,"E002",supports=["C001"])
        cl(ws,"C001",evidence=["E001","E002"],support_sets=[["E001"],["E002"]])
        res=apply_evidence_revision(ws,{"E001":"superseded"},reason="one alternative removed")
        status=ClaimModel.load(ws.claims_dir/"C001.md").status
        return {
            "passed": status=="supported" and not res["claim_changes"],
            "claim_status_after": status,
            "claim_changes": res["claim_changes"],
        }



def exhaustive_write_position_rollback() -> dict:
    """Fail each entity-write position in an 11-file revision and require exact rollback."""
    trials=[]
    for fail_at in range(1,12):
        with tempfile.TemporaryDirectory() as td:
            ws=init_workspace(Path(td))
            # One evidence item supports ten singleton claims -> 11 changed entity files.
            claim_ids=[f"C{i:03d}" for i in range(1,11)]
            ev(ws,"E001",supports=claim_ids)
            for cid in claim_ids:
                cl(ws,cid,evidence=["E001"])
            paths=[ws.evidence_dir/"E001.md", *[ws.claims_dir/f"{cid}.md" for cid in claim_ids]]
            before={str(p):digest(p) for p in paths}
            original=rev.atomic_write_text
            state={"n":0,"raised":False}
            def flaky(path,text):
                if "research" in Path(path).parts and not state["raised"]:
                    state["n"] += 1
                    if state["n"] == fail_at:
                        state["raised"] = True
                        raise OSError(f"injected entity-write failure at position {fail_at}")
                return original(path,text)
            rev.atomic_write_text=flaky
            try:
                try:
                    apply_evidence_revision(ws,{"E001":"superseded"},reason=f"fail-at-{fail_at}")
                except OSError:
                    pass
            finally:
                rev.atomic_write_text=original
            after={str(p):digest(p) for p in paths}
            manifests=list((ws.root/".researchledger"/"revisions").glob("*/manifest.json"))
            phase=json.loads(manifests[0].read_text())["phase"] if manifests else None
            trials.append({"fail_at":fail_at,"restored":before==after,"phase":phase})
    return {
        "passed": all(t["restored"] and t["phase"]=="rolled_back" for t in trials),
        "n_positions": len(trials),
        "n_restored": sum(t["restored"] for t in trials),
        "trials": trials,
    }


def concurrent_independent_writers() -> dict:
    """Launch two revision CLIs simultaneously and verify serialization preserves both commits."""
    repo_root=Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as td:
        ws=init_workspace(Path(td))
        ev(ws,"E001",supports=["C001"]); cl(ws,"C001",evidence=["E001"])
        ev(ws,"E002",supports=["C002"]); cl(ws,"C002",evidence=["E002"])
        env=os.environ.copy(); env["PYTHONPATH"]=str(repo_root)
        commands=[
            [sys.executable,"-m","researchledger.cli","revision","apply","--update","E001=superseded","--reason","concurrent-1","--json"],
            [sys.executable,"-m","researchledger.cli","revision","apply","--update","E002=superseded","--reason","concurrent-2","--json"],
        ]
        procs=[subprocess.Popen(c,cwd=td,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for c in commands]
        completed=[]
        for p in procs:
            out,err=p.communicate(timeout=30)
            completed.append({"returncode":p.returncode,"stdout":out,"stderr_nonempty":bool(err.strip())})
        statuses={
            "E001":EvidenceModel.load(ws.evidence_dir/"E001.md").status,
            "E002":EvidenceModel.load(ws.evidence_dir/"E002.md").status,
            "C001":ClaimModel.load(ws.claims_dir/"C001.md").status,
            "C002":ClaimModel.load(ws.claims_dir/"C002.md").status,
        }
        txs=list((ws.root/".researchledger"/"revisions").glob("*/manifest.json"))
        phases=[json.loads(p.read_text())["phase"] for p in txs]
        return {
            "passed": all(x["returncode"]==0 for x in completed)
                      and statuses=={"E001":"superseded","E002":"superseded","C001":"hypothesis","C002":"hypothesis"}
                      and phases.count("committed")==2,
            "processes":completed,
            "final_statuses":statuses,
            "transaction_phases":sorted(phases),
        }


def main():
    checks={
        "normal_commit":normal_commit(),
        "mid_write_failure_rolls_back":mid_write_failure_rolls_back(),
        "crash_recovery_restores":crash_recovery_restores(),
        "alternative_support_selectivity":alternative_support_selectivity(),
        "exhaustive_write_position_rollback":exhaustive_write_position_rollback(),
        "concurrent_independent_writers":concurrent_independent_writers(),
    }
    payload={
        "schema":"researchledger-transaction-fault-injection-1",
        "scope":"Local deterministic fault injection against the application-level revision transaction; not a distributed database durability claim.",
        "n_checks":len(checks),
        "n_passed":sum(bool(x["passed"]) for x in checks.values()),
        "checks":checks,
    }
    OUT.write_text(json.dumps(payload,indent=2)+"\n")
    print(json.dumps({"n_checks":payload["n_checks"],"n_passed":payload["n_passed"]},indent=2))

if __name__=="__main__": main()
