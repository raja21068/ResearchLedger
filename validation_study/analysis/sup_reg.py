"""SUP and REG rebuilt on the ResearchLedger package (2026-11-25).

New experiments on `researchledger`; they do NOT reproduce the TRL-package
SUP-300 / REG results of the CMC 95532 manuscript (that code is lost).

Unit of analysis: claims (ResearchLedger propagates evidence revisions to claim
status only; manuscript assertions and decisions are not modelled).
Ground truth: the oracle of `tms_crosscheck` evaluated on the GOLD relations.
Each system is evaluated on the REGISTERED relations (= gold in SUP, a
corrupted copy in REG).

After every revision event, over claims that were live at trajectory start:
  recall  = truly dead claims the system marks dead / truly dead claims
  FIR     = truly live claims the system marks dead / truly live claims
  escape  = truly dead claims the system still marks live / truly dead claims
Counts are pooled over events; 95% CIs are percentile bootstrap over
trajectories (1,000 resamples).

Usage:
  python -m validation_study.analysis.sup_reg --n 300 --seed 61
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validation_study.analysis.tms_crosscheck import (  # noqa: E402
    build_rl_claims,
    flat_live,
    generate_trajectory,
    oracle_live,
    reach_live,
    rl_live,
)

SYSTEMS = ("no_state", "reachability", "flat_edges", "rl_naive", "rl_explicit")


def system_live(name, rels, claims, status, cache):
    if name == "no_state":
        return {c: True for c in claims}
    if name == "reachability":
        return reach_live(rels, claims, status)
    if name == "flat_edges":
        return flat_live(rels, claims, status)
    mode = name.split("_", 1)[1]
    if mode not in cache:
        cache[mode] = build_rl_claims(rels, claims, mode)
    return rl_live(cache[mode], status)


def corrupt(traj, rng, *, drop=0.0, flatten=0.0, spurious=0.0):
    rels = []
    groups = {(c, g) for _e, c, k, g in traj["relations"] if k == "member"}
    flat_groups = {cg for cg in sorted(groups) if rng.random() < flatten}
    for e, c, k, g in traj["relations"]:
        if rng.random() < drop:
            continue
        if k == "member" and (c, g) in flat_groups:
            rels.append((e, c, "supports", None))
        else:
            rels.append((e, c, k, g))
    for _ in range(round(spurious * len(traj["relations"]))):
        rels.append((rng.choice(traj["evidence"]), rng.choice(traj["claims"]), "supports", None))
    return rels


def coverage(gold, reg, claims):
    """Edge recall and support-set coverage of the registered graph."""
    gold_set = {(e, c, k) for e, c, k, _ in gold}
    reg_set = {(e, c, k) for e, c, k, _ in reg}
    edge_recall = len(gold_set & reg_set) / len(gold_set) if gold_set else 1.0

    def paths(rels, c):
        singles = {frozenset([e]) for e, cc, k, _ in rels if cc == c and k == "supports"}
        groups = defaultdict(set)
        for e, cc, k, g in rels:
            if cc == c and k == "member":
                groups[g].add(e)
        return singles | {frozenset(v) for v in groups.values()}

    total = kept = 0
    for c in claims:
        gp = paths(gold, c)
        rp = paths(reg, c)
        total += len(gp)
        kept += len(gp & rp)
    return edge_recall, (kept / total if total else 1.0)


def evaluate(trajs, rel_fn, seed_tag):
    """Per-trajectory counts for every system."""
    rng = random.Random(seed_tag)
    per_traj = []
    recall_parts, cov_parts = [], []
    for traj in trajs:
        reg = rel_fn(traj, rng)
        gold = traj["relations"]
        claims = traj["claims"]
        er, sc = coverage(gold, reg, claims)
        recall_parts.append(er)
        cov_parts.append(sc)
        status = dict(traj["status0"])
        start = oracle_live(gold, claims, status)
        tracked = [c for c in claims if start[c]]
        cache: dict = {}
        counts = {s: defaultdict(int) for s in SYSTEMS}
        by_template = {s: defaultdict(lambda: defaultdict(int)) for s in SYSTEMS}
        for ev in traj["events"]:
            status.update(ev)
            truth = oracle_live(gold, claims, status)
            for s in SYSTEMS:
                got = system_live(s, reg, claims, status, cache)
                cnt = counts[s]
                for c in tracked:
                    t = traj["templates"][c]
                    if truth[c]:
                        cnt["live"] += 1
                        by_template[s][t]["live"] += 1
                        if not got[c]:
                            cnt["false_inval"] += 1
                            by_template[s][t]["false_inval"] += 1
                    else:
                        cnt["dead"] += 1
                        by_template[s][t]["dead"] += 1
                        if got[c]:
                            cnt["escape"] += 1
                            by_template[s][t]["escape"] += 1
        per_traj.append({"counts": counts, "by_template": by_template})
    return per_traj, sum(recall_parts) / len(recall_parts), sum(cov_parts) / len(cov_parts)


def pooled(per_traj, system, idx=None, template=None):
    tot = defaultdict(int)
    rows = per_traj if idx is None else [per_traj[i] for i in idx]
    for r in rows:
        src = r["counts"][system] if template is None else r["by_template"][system].get(template, {})
        for k, v in src.items():
            tot[k] += v
    dead, live = tot["dead"], tot["live"]
    return {
        "dead": dead,
        "live": live,
        "recall": (dead - tot["escape"]) / dead if dead else None,
        "escape": tot["escape"] / dead if dead else None,
        "fir": tot["false_inval"] / live if live else None,
    }


def bootstrap_ci(per_traj, system, metric, n_boot=1000, seed=0):
    rng = random.Random(seed)
    n = len(per_traj)
    vals = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        v = pooled(per_traj, system, idx)[metric]
        if v is not None:
            vals.append(v)
    vals.sort()
    if not vals:
        return None
    return [vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]]


def summarize(per_traj, systems=SYSTEMS, ci=True):
    out = {}
    for s in systems:
        p = pooled(per_traj, s)
        if ci:
            for m in ("recall", "escape", "fir"):
                p[f"{m}_ci95"] = bootstrap_ci(per_traj, s, m)
        out[s] = p
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SUP/REG on researchledger")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=61)
    ap.add_argument("--out", type=Path, default=ROOT / "validation_study" / "results" / "sup_reg.json")
    args = ap.parse_args(argv)

    rng = random.Random(args.seed)
    trajs = [generate_trajectory(rng, i) for i in range(args.n)]
    templates = sorted({t for tr in trajs for t in tr["templates"].values()})

    # SUP: perfect registration
    sup_traj, _, _ = evaluate(trajs, lambda tr, r: list(tr["relations"]), f"{args.seed}-sup")
    sup = {
        "overall": summarize(sup_traj),
        "by_template": {
            t: {s: pooled(sup_traj, s, template=t) for s in SYSTEMS} for t in templates
        },
    }

    # REG: registration corruption sweeps (system on corrupted graph, truth on gold)
    sweeps = {
        "drop": [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
        "flatten": [0.0, 0.25, 0.5, 0.75, 1.0],
        "spurious": [0.0, 0.05, 0.10, 0.20, 0.30],
    }
    reg = {}
    for kind, rates in sweeps.items():
        reg[kind] = []
        for rate in rates:
            fn = lambda tr, r, k=kind, x=rate: corrupt(tr, r, **{k: x})  # noqa: E731
            pt, er, sc = evaluate(trajs, fn, f"{args.seed}-{kind}-{rate}")
            reg[kind].append({
                "rate": rate,
                "edge_recall": er,
                "support_set_coverage": sc,
                "systems": summarize(pt, systems=("rl_explicit", "flat_edges", "reachability"),
                                     ci=True),
            })

    result = {"n": args.n, "seed": args.seed, "unit": "claim-event", "sup": sup, "reg": reg}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    f = lambda v: "  -  " if v is None else f"{v:.3f}"  # noqa: E731
    print(f"SUP (perfect registration), n={args.n}, seed={args.seed}")
    print(f"{'system':<14}{'recall':>8}{'FIR':>8}{'escape':>8}   escape 95% CI")
    for s, p in sup["overall"].items():
        print(f"{s:<14}{f(p['recall']):>8}{f(p['fir']):>8}{f(p['escape']):>8}   {p['escape_ci95']}")
    print("\nSUP recall by template (rl_explicit / flat_edges / reachability):")
    for t in templates:
        row = sup["by_template"][t]
        print(f"  {t:<12} " + " / ".join(f(row[s]["recall"]) for s in ("rl_explicit", "flat_edges", "reachability"))
              + "   FIR: " + " / ".join(f(row[s]["fir"]) for s in ("rl_explicit", "flat_edges", "reachability")))
    print("\nREG (rl_explicit on corrupted registration; truth on gold)")
    for kind, pts in reg.items():
        for p in pts:
            s = p["systems"]["rl_explicit"]
            print(f"  {kind:<9}{p['rate']:>5.2f}  edge_recall={p['edge_recall']:.3f} "
                  f"set_cov={p['support_set_coverage']:.3f}  escape={f(s['escape'])} "
                  f"{s['escape_ci95']}  FIR={f(s['fir'])}  flat_escape={f(p['systems']['flat_edges']['escape'])}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
