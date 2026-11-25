"""TMS-XC rebuilt on the ResearchLedger package (2026-11-25).

Executable cross-check of ResearchLedger's AND/OR support-set derivation
(`researchledger.models.recompute_claim_status`) against three independently
written formulations of the same semantics:

* an oracle that evaluates the registered relation list directly;
* a Doyle-style JTMS (forward-fixpoint labelling over justifications);
* a de Kleer-style ATMS (minimal environment labels, then subset tests).

None of the three imports or calls ResearchLedger code.

This is a NEW experiment on a different implementation from the TRL package
(`research/ledger`, `eval/tms_crosscheck.py`) reported in the CMC 95532
manuscript. That code could not be located; its 3,551/3,600 figure is not
reproduced here and these numbers do not replace it.

Scope: ResearchLedger propagates evidence revisions to claim status only.
Decisions, manuscript assertions, lineage closure and non-epistemic
dependencies of the TRL paper are not modelled by ResearchLedger and are not
part of this check.

Registered relations are triples (evidence, claim, kind, group):
  supports -> evidence is a singleton sufficient path for the claim
  member   -> evidence is one conjunct of sufficient set `group`
  requires -> evidence is a premise conjoined with every sufficient path

A claim is live iff every premise is live and at least one sufficient path
has all members live. Evidence is live unless invalidated or superseded.

Two ways of writing relations into ResearchLedger claim frontmatter are
compared ("registration modes"):
  naive    -> supports edges go to `claim.evidence`; groups to
              `support_sets`. ResearchLedger then ignores the singleton path of
              any evidence that also appears in a group (pair collision).
  explicit -> once a claim has any group, every sufficient path, including
              singletons, is written to `support_sets`
              (`researchledger.models.support_fields_from_relations`).

Usage:
  python -m validation_study.analysis.tms_crosscheck --n 300 --seed 61
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from researchledger.models import (  # noqa: E402
    Claim,
    Evidence,
    recompute_claim_status,
    support_fields_from_relations,
)

DEAD = {"invalidated", "superseded"}
LIVE_CLAIM = {"supported", "provisional", "mixed"}
EVENTS_PER_TRAJECTORY = 3
IMPLS = ("jtms", "atms", "rl_naive", "rl_explicit", "reach", "flat")
CONTROLS = ("reach", "flat")

# --------------------------------------------------------------------------
# Synthetic trajectories
# --------------------------------------------------------------------------

TEMPLATES = ("single", "conjunctive", "alternative", "alt_groups", "required", "mixed")


def generate_trajectory(rng: random.Random, tid: int) -> dict:
    n_ev = rng.randint(8, 14)
    n_cl = rng.randint(4, 8)
    evidence = [f"E{tid:03d}{i:02d}" for i in range(n_ev)]
    claims = [f"C{tid:03d}{i:02d}" for i in range(n_cl)]
    rels: list[tuple[str, str, str, str | None]] = []
    templates = {}
    for c in claims:
        t = rng.choice(TEMPLATES)
        templates[c] = t
        pick = lambda k: rng.sample(evidence, k)  # noqa: E731
        if t == "single":
            rels.append((pick(1)[0], c, "supports", None))
        elif t == "conjunctive":
            for e in pick(rng.randint(2, 3)):
                rels.append((e, c, "member", "g1"))
        elif t == "alternative":
            g = pick(rng.randint(2, 3))
            for e in g:
                rels.append((e, c, "member", "g1"))
            rest = [e for e in evidence if e not in g]
            rels.append((rng.choice(rest), c, "supports", None))
        elif t == "alt_groups":
            ids = pick(4)
            for e in ids[:2]:
                rels.append((e, c, "member", "g1"))
            for e in ids[2:]:
                rels.append((e, c, "member", "g2"))
        elif t == "required":
            ids = pick(3)
            rels.append((ids[0], c, "supports", None))
            rels.append((ids[1], c, "supports", None))
            rels.append((ids[2], c, "requires", None))
        else:  # mixed: group + singleton + premise
            ids = pick(4)
            rels.append((ids[0], c, "member", "g1"))
            rels.append((ids[1], c, "member", "g1"))
            rels.append((ids[2], c, "supports", None))
            rels.append((ids[3], c, "requires", None))
    status0 = {e: rng.choice(["verified", "verified", "checked"]) for e in evidence}
    events = []
    live = list(evidence)
    for _ in range(EVENTS_PER_TRAJECTORY):
        k = min(len(live), rng.choice([1, 1, 2]))
        targets = rng.sample(live, k)
        live = [e for e in live if e not in targets]
        events.append({e: rng.choice(["invalidated", "superseded"]) for e in targets})
    return {
        "tid": tid,
        "evidence": evidence,
        "claims": claims,
        "templates": templates,
        "relations": rels,
        "status0": status0,
        "events": events,
    }


def corrupt(traj: dict, graph: str, rng: random.Random) -> list[tuple]:
    rels = list(traj["relations"])
    if graph == "gold":
        return rels
    if graph == "drop20":
        return [r for r in rels if rng.random() >= 0.20]
    if graph == "flatten":
        return [(e, c, "supports", None) if k == "member" else (e, c, k, g) for e, c, k, g in rels]
    if graph == "spurious30":
        extra = round(0.30 * len(rels))
        for _ in range(extra):
            rels.append((rng.choice(traj["evidence"]), rng.choice(traj["claims"]), "supports", None))
        return rels
    raise ValueError(graph)


# --------------------------------------------------------------------------
# Independent formulations (no ResearchLedger imports)
# --------------------------------------------------------------------------

def _paths(rels, claim):
    """Return (sufficient paths, premises) for a claim from raw relations."""
    singles, groups, req = [], {}, set()
    for e, c, k, g in rels:
        if c != claim:
            continue
        if k == "supports":
            singles.append(frozenset([e]))
        elif k == "member":
            groups.setdefault(g, set()).add(e)
        elif k == "requires":
            req.add(e)
    return singles + [frozenset(s) for s in groups.values()], frozenset(req)


def oracle_live(rels, claims, status):
    alive = {e for e, s in status.items() if s not in DEAD}
    out = {}
    for c in claims:
        paths, req = _paths(rels, c)
        out[c] = req <= alive and any(p <= alive for p in paths)
    return out


def jtms_live(rels, claims, status):
    """Doyle-style JTMS: justifications (antecedents -> consequent); premises
    are the live evidence nodes; labels found by forward propagation to a
    fixpoint."""
    justs = []  # (antecedent set, consequent)
    for c in claims:
        paths, req = _paths(rels, c)
        for p in paths:
            justs.append((set(p) | set(req), c))
    label_in = {e for e, s in status.items() if s not in DEAD}
    changed = True
    while changed:
        changed = False
        for ante, cons in justs:
            if cons not in label_in and ante <= label_in:
                label_in.add(cons)
                changed = True
    return {c: c in label_in for c in claims}


def _cited(rels, claim):
    return {e for e, c, _k, _g in rels if c == claim}


def reach_live(rels, claims, status):
    """Negative control: downstream reachability. Any dead cited record
    invalidates the claim (ignores alternatives)."""
    alive = {e for e, s in status.items() if s not in DEAD}
    return {c: bool(_cited(rels, c)) and _cited(rels, c) <= alive for c in claims}


def flat_live(rels, claims, status):
    """Negative control: flat binary edges. Any live cited record keeps the
    claim alive (ignores conjunctions and premises)."""
    alive = {e for e, s in status.items() if s not in DEAD}
    return {c: bool(_cited(rels, c) & alive) for c in claims}


def _minimize(envs):
    envs = sorted(set(envs), key=len)
    kept = []
    for env in envs:
        if not any(k <= env for k in kept):
            kept.append(env)
    return kept


def atms_labels(rels, claims):
    labels = {}
    for c in claims:
        paths, req = _paths(rels, c)
        labels[c] = _minimize(frozenset(p | req) for p in paths)
    return labels


def atms_live(labels, claims, status):
    alive = {e for e, s in status.items() if s not in DEAD}
    return {c: any(env <= alive for env in labels[c]) for c in claims}


# --------------------------------------------------------------------------
# ResearchLedger under test
# --------------------------------------------------------------------------

def _naive_fields(rels, claim):
    evidence, groups, req = [], {}, []
    for e, c, k, g in rels:
        if c != claim:
            continue
        if k == "supports" and e not in evidence:
            evidence.append(e)
        elif k == "member":
            groups.setdefault(g, []).append(e)
        elif k == "requires" and e not in req:
            req.append(e)
    for members in groups.values():
        for e in members:
            if e not in evidence:
                evidence.append(e)
    return {
        "evidence": evidence,
        "support_sets": [sorted(set(m)) for _, m in sorted(groups.items())],
        "required_evidence": ",".join(req) or None,
    }


def build_rl_claims(rels, claims, mode):
    out = {}
    for c in claims:
        if mode == "naive":
            fields = _naive_fields(rels, c)
        else:
            fields = support_fields_from_relations([r for r in rels if r[1] == c])
        out[c] = Claim(id=c, path=Path(f"{c}.md"), status="hypothesis", **fields)
    return out


def rl_live(rl_claims, status):
    ev = {e: Evidence(id=e, path=Path(f"{e}.md"), status=s) for e, s in status.items()}
    return {c: recompute_claim_status(cl, ev) in LIVE_CLAIM for c, cl in rl_claims.items()}


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------

def affected(before, after):
    return frozenset(c for c in before if before[c] != after[c])


def has_pair_collision(rels, claim):
    kinds = {}
    for e, c, k, _ in rels:
        if c == claim:
            kinds.setdefault(e, set()).add(k)
    return any({"supports", "member"} <= ks for ks in kinds.values())


def run(n: int, seed: int, graphs=("gold", "drop20", "flatten", "spurious30")) -> dict:
    rng = random.Random(seed)
    trajs = [generate_trajectory(rng, i) for i in range(n)]
    results = {}
    for graph in graphs:
        crng = random.Random(f"{seed}-{graph}")
        tallies = Counter()
        divergences = []
        for traj in trajs:
            rels = corrupt(traj, graph, crng)
            claims = traj["claims"]
            labels = atms_labels(rels, claims)
            rl_naive = build_rl_claims(rels, claims, "naive")
            rl_explicit = build_rl_claims(rels, claims, "explicit")
            status = dict(traj["status0"])
            prev = {
                "oracle": oracle_live(rels, claims, status),
                "jtms": jtms_live(rels, claims, status),
                "atms": atms_live(labels, claims, status),
                "rl_naive": rl_live(rl_naive, status),
                "rl_explicit": rl_live(rl_explicit, status),
                "reach": reach_live(rels, claims, status),
                "flat": flat_live(rels, claims, status),
            }
            for ei, ev in enumerate(traj["events"]):
                status.update(ev)
                cur = {
                    "oracle": oracle_live(rels, claims, status),
                    "jtms": jtms_live(rels, claims, status),
                    "atms": atms_live(labels, claims, status),
                    "rl_naive": rl_live(rl_naive, status),
                    "rl_explicit": rl_live(rl_explicit, status),
                    "reach": reach_live(rels, claims, status),
                    "flat": flat_live(rels, claims, status),
                }
                gold_set = affected(prev["oracle"], cur["oracle"])
                tallies["events"] += 1
                tallies["nonempty"] += bool(gold_set)
                for name in IMPLS:
                    got = affected(prev[name], cur[name])
                    if got == gold_set:
                        tallies[name] += 1
                    else:
                        diff = sorted(got ^ gold_set)
                        cause = (
                            "pair_collision"
                            if all(has_pair_collision(rels, c) for c in diff)
                            else "other"
                        )
                        tallies[f"{name}:{cause}"] += 1
                        if name in CONTROLS:
                            continue
                        divergences.append(
                            {"impl": name, "tid": traj["tid"], "event": ei, "claims": diff, "cause": cause}
                        )
                prev = cur
        results[graph] = {"tallies": dict(tallies), "divergences": divergences}
    return {"n": n, "seed": seed, "events_per_trajectory": EVENTS_PER_TRAJECTORY, "graphs": results}


# --------------------------------------------------------------------------
# On-disk check: the real revision planner agrees with the direct call
# --------------------------------------------------------------------------

def planner_check(n: int, seed: int, graph: str = "spurious30", mode: str = "explicit") -> dict:
    """Materialize trajectories as real workspaces and compare
    `plan_evidence_revision`'s claim liveness changes with the oracle."""
    from researchledger.revision import plan_evidence_revision
    from researchledger.workspace import init_workspace

    rng = random.Random(seed)
    trajs = [generate_trajectory(rng, i) for i in range(n)]
    crng = random.Random(f"{seed}-{graph}")
    events = matches = 0
    with tempfile.TemporaryDirectory() as tmp:
        for traj in trajs:
            rels = corrupt(traj, graph, crng)
            claims = traj["claims"]
            rl_claims = build_rl_claims(rels, claims, mode)
            ws = init_workspace(Path(tmp) / f"t{traj['tid']}")
            status = dict(traj["status0"])
            for ei, ev in enumerate(traj["events"]):
                ev_objs = {}
                for e, s in status.items():
                    obj = Evidence(id=e, path=ws.evidence_dir / f"{e}.md", schema_version="2.0",
                                   name=e, status=s, source_kind="observation", body=f"# {e}\n")
                    obj.path.write_text(obj.render(), encoding="utf-8")
                    ev_objs[e] = obj
                for c, cl in rl_claims.items():
                    cl.path = ws.claims_dir / f"{c}.md"
                    cl.schema_version, cl.name, cl.body = "2.0", c, f"## Statement\n{c}\n"
                    cl.status = recompute_claim_status(cl, ev_objs)
                    cl.path.write_text(cl.render(), encoding="utf-8")
                plan = plan_evidence_revision(ws, ev, reason=f"event {ei}")
                planner_set = frozenset(
                    ch.entity_id for ch in plan.claim_changes
                    if (ch.before in LIVE_CLAIM) != (ch.after in LIVE_CLAIM)
                )
                before = oracle_live(rels, claims, status)
                status.update(ev)
                after = oracle_live(rels, claims, status)
                events += 1
                matches += planner_set == affected(before, after)
    return {"graph": graph, "mode": mode, "trajectories": n, "events": events, "matches": matches}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=61)
    ap.add_argument("--planner-n", type=int, default=30,
                    help="trajectories materialized on disk for the planner check")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "validation_study" / "results" / "tms_crosscheck.json")
    args = ap.parse_args(argv)

    result = run(args.n, args.seed)
    result["planner_check"] = [
        planner_check(args.planner_n, args.seed, g, m)
        for g in ("gold", "spurious30") for m in ("naive", "explicit")
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    cols = ("events", "nonempty") + IMPLS
    print(f"TMS-XC on ResearchLedger, n={args.n}, seed={args.seed}")
    print("graph        " + " ".join(f"{c:>11}" for c in cols) + "   naive divergence causes")
    for g, r in result["graphs"].items():
        t = r["tallies"]
        causes = {k.split(":", 1)[1]: v for k, v in t.items() if k.startswith("rl_naive:")}
        other = {k: v for k, v in t.items() if ":" in k
                 and k.split(":")[0] not in ("rl_naive",) + CONTROLS}
        print(f"{g:<12} " + " ".join(f"{t.get(c, 0):>11}" for c in cols) + f"   {causes or '-'}"
              + (f"  OTHER IMPL DIVERGENCES: {other}" if other else ""))
    for pc in result["planner_check"]:
        print(f"planner check {pc['graph']:<10} {pc['mode']:<8}: {pc['matches']}/{pc['events']}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
