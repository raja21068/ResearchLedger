"""Scaling of one evidence revision in ResearchLedger (2026-11-25).

New experiment on `researchledger`; it does NOT reproduce the TRL-package
scaling study (single JSON snapshot rewritten per commit) of the CMC 95532
manuscript. ResearchLedger stores one Markdown file per record and a revision
rewrites only the changed files.

Workspace of size N "triples": N evidence records, N claims and N decisions.
Claim i is supported by evidence i (and, for every 4th claim, alternatively by
evidence i+1). One revision supersedes a single evidence record (its claim loses its only
support path and moves to hypothesis).

Measured per size (median over repeats, each on a fresh copy of the same
workspace, after one untimed warm-up validation so that cold file-cache and
on-access antivirus costs on freshly copied files are excluded):
  plan_s     plan_evidence_revision (load + recompute every claim)
  validate_s one full validate(ws) call
  apply_s    apply_evidence_revision end to end (lock, recovery scan, plan,
             freshness, validation before and after, journal, writes)
  bytes_written  bytes of ledger files rewritten by the commit
  workspace_bytes total size of research/ records

Usage:
  python -m validation_study.analysis.revision_scaling --sizes 1000 3000 10000 30000
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from researchledger.models import Claim, Decision, Evidence  # noqa: E402
from researchledger.revision import apply_evidence_revision, plan_evidence_revision  # noqa: E402
from researchledger.validator import validate  # noqa: E402
from researchledger.workspace import init_workspace  # noqa: E402


def build(root: Path, n: int):
    ws = init_workspace(root)
    for i in range(n):
        eid, cid, did = f"E{i + 1:06d}", f"C{i + 1:06d}", f"D{i + 1:06d}"
        supports = [cid] + ([f"C{i:06d}"] if i % 4 == 1 else [])
        ev = Evidence(id=eid, path=ws.evidence_dir / f"{eid}.md", schema_version="2.0", name=eid,
                      status="verified", source_kind="observation", supports=supports,
                      body=f"# {eid}\n")
        ev.path.write_text(ev.render(), encoding="utf-8")
        alt = i % 4 == 0 and i + 1 < n
        ev_ids = [eid] + ([f"E{i + 2:06d}"] if alt else [])
        cl = Claim(id=cid, path=ws.claims_dir / f"{cid}.md", schema_version="2.0", name=cid,
                   status="supported", evidence=ev_ids,
                   support_sets=[[e] for e in ev_ids] if alt else [],
                   body=f"## Statement\n{cid}\n")
        cl.path.write_text(cl.render(), encoding="utf-8")
        dec = Decision(id=did, path=ws.decisions_dir / f"{did}.md", schema_version="2.0", name=did,
                       status="decided", evidence=[eid], body=f"# {did}\n")
        dec.path.write_text(dec.render(), encoding="utf-8")
    return ws


def dir_bytes(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def measure(n: int, repeats: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "base"
        t0 = time.perf_counter()
        ws = build(base, n)
        build_s = time.perf_counter() - t0
        pre = validate(ws)
        if pre.errors:
            raise RuntimeError(f"fixture has validation errors: {[i.message for i in pre.errors[:3]]}")
        idx = n // 2 - (n // 2) % 4 + 2  # i % 4 == 2: no alternative path, claim must change
        target = f"E{idx + 1:06d}"
        rows = []
        for r in range(repeats):
            copy = Path(tmp) / f"r{r}"
            shutil.copytree(base, copy)
            wsr = init_workspace(copy) if not (copy / "project.md").exists() else type(ws)(copy)
            validate(wsr)  # untimed warm-up: first read of freshly copied files is cold
            t = time.perf_counter(); plan = plan_evidence_revision(wsr, {target: "superseded"})
            plan_s = time.perf_counter() - t
            t = time.perf_counter(); validate(wsr)
            validate_s = time.perf_counter() - t
            t = time.perf_counter(); res = apply_evidence_revision(wsr, {target: "superseded"})
            apply_s = time.perf_counter() - t
            written = sum((copy / rel).stat().st_size for rel in res["files"])
            rows.append({"plan_s": plan_s, "validate_s": validate_s, "apply_s": apply_s,
                         "files_written": len(res["files"]), "bytes_written": written,
                         "claim_changes": len(plan.claim_changes)})
            shutil.rmtree(copy, ignore_errors=True)
        med = {k: statistics.median(row[k] for row in rows) for k in rows[0]}
        return {"triples": n, "records": 3 * n, "repeats": repeats, "build_s": build_s,
                "workspace_bytes": dir_bytes(base / "research"), "median": med, "runs": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ResearchLedger revision scaling")
    ap.add_argument("--sizes", type=int, nargs="+", default=[1000, 3000, 10000, 30000])
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", type=Path, default=ROOT / "validation_study" / "results" / "revision_scaling.json")
    args = ap.parse_args(argv)
    results = []
    for n in args.sizes:
        r = measure(n, args.repeats)
        m = r["median"]
        print(f"triples={n:>7} records={3 * n:>7}  plan={m['plan_s']:.2f}s  validate={m['validate_s']:.2f}s  "
              f"apply={m['apply_s']:.2f}s  files_written={m['files_written']:.0f}  "
              f"bytes_written={m['bytes_written']:.0f}  workspace={r['workspace_bytes'] / 1e6:.1f} MB", flush=True)
        results.append(r)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"machine": platform.platform(), "python": platform.python_version(),
                                        "processor": platform.processor(), "results": results}, indent=2),
                            encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
