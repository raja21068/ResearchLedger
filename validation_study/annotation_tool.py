from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKETS = ROOT / "annotation_packets"
SOURCE_CASES = ROOT / "source_cases"

FIELDS = ("affected_claims", "unaffected_claims", "affected_decisions", "affected_assertions")


def _list_value(q: dict, field: str) -> list[str]:
    value = (q.get(field) or {}).get("value")
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field}.value must be a list or null")
    return [str(x) for x in value]


def make_packet(case: dict) -> dict:
    return {
        "schema": "prr-blind-annotation-packet-1",
        "trajectory_id": case["id"],
        "source": case["source"],
        "objects": case["objects"],
        "revision_event": case["mutations"][0],
        "instructions": [
            "Annotate from the historical source/diff and object descriptions only.",
            "Do not infer labels from any TRL/system output; none is included in this packet.",
            "Mark an object affected only when the revision removes a dependency needed for that object to remain valid.",
            "For claims, distinguish conjunctive support (all members required) from alternative sufficient paths.",
            "If the supplied context is insufficient, use overall_sufficient_context=false rather than guessing.",
        ],
        "questions": {
            "affected_claims": {"value": None, "confidence": None, "rationale": None},
            "unaffected_claims": {"value": None, "confidence": None, "rationale": None},
            "affected_decisions": {"value": None, "confidence": None, "rationale": None},
            "affected_assertions": {"value": None, "confidence": None, "rationale": None},
            "support_relations": {"value": None, "confidence": None, "rationale": None},
            "overall_sufficient_context": {"value": None, "rationale": None},
        },
    }


def generate_packets() -> int:
    PACKETS.mkdir(parents=True, exist_ok=True)
    expected = set()
    for path in sorted(SOURCE_CASES.glob("*.json")):
        case = json.loads(path.read_text())
        name = f"{case['id']}.blind.json"
        expected.add(name)
        out = PACKETS / name
        out.write_text(json.dumps(make_packet(case), indent=2) + "\n")
    # Keep the packet directory a deterministic projection of source_cases so
    # superseded pilot packets cannot silently enter an annotation round.
    for stale in PACKETS.glob("*.blind.json"):
        if stale.name not in expected:
            stale.unlink()
    manifest = {
        "schema": "prr-annotation-packet-manifest-1",
        "n_packets": len(expected),
        "packets": sorted(expected),
        "note": "Packets contain no system predictions or gold labels. Completion requires independent annotators; blank packets are not evidence of agreement.",
    }
    (PACKETS / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"generated {len(expected)} blind packets in {PACKETS}")
    return 0


def _binary_kappa(labels_a: list[int], labels_b: list[int]) -> float | None:
    if len(labels_a) != len(labels_b) or not labels_a:
        return None
    n = len(labels_a)
    po = sum(a == b for a, b in zip(labels_a, labels_b)) / n
    pa1 = sum(labels_a) / n; pb1 = sum(labels_b) / n
    pe = pa1 * pb1 + (1-pa1) * (1-pb1)
    if pe == 1:
        return 1.0 if po == 1 else None
    return (po - pe) / (1 - pe)


def score_pair(path_a: Path, path_b: Path) -> dict:
    a = json.loads(path_a.read_text()); b = json.loads(path_b.read_text())
    if a.get("trajectory_id") != b.get("trajectory_id"):
        raise ValueError("annotation files have different trajectory_id values")
    case_path = SOURCE_CASES / f"{a['trajectory_id']}.json"
    case = json.loads(case_path.read_text())
    q_a = a.get("questions", {}); q_b = b.get("questions", {})
    out = {"trajectory_id": a["trajectory_id"], "fields": {}}
    for field in FIELDS:
        va, vb = set(_list_value(q_a, field)), set(_list_value(q_b, field))
        exact = va == vb
        inter = len(va & vb); union = len(va | vb)
        out["fields"][field] = {
            "exact_agreement": exact,
            "jaccard": 1.0 if union == 0 else inter / union,
            "annotator_a": sorted(va),
            "annotator_b": sorted(vb),
        }
    # Object-level kappa over claims, decisions and assertions.  Unaffected-claim labels
    # are not pooled with affected labels; the primary impact task is affected/not-affected.
    kind_map = {"affected_claims":"claims", "affected_decisions":"decisions", "affected_assertions":"assertions"}
    labels_a=[]; labels_b=[]
    for field, kind in kind_map.items():
        aa=set(_list_value(q_a, field)); bb=set(_list_value(q_b, field))
        for oid in sorted(case["objects"].get(kind, {})):
            labels_a.append(int(oid in aa)); labels_b.append(int(oid in bb))
    out["pooled_object_level"] = {
        "n_labels": len(labels_a),
        "percent_agreement": None if not labels_a else sum(x==y for x,y in zip(labels_a,labels_b))/len(labels_a),
        "cohen_kappa": _binary_kappa(labels_a, labels_b),
    }
    return out



def _load_annotation_dir(directory: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        tid = payload.get("trajectory_id")
        if tid:
            out[str(tid)] = path
    return out


def aggregate_dirs(dir_a: Path, dir_b: Path) -> dict:
    a_files = _load_annotation_dir(dir_a)
    b_files = _load_annotation_dir(dir_b)
    shared = sorted(set(a_files) & set(b_files))
    if not shared:
        raise ValueError("no matching trajectory_id values across annotation directories")

    pair_scores = [score_pair(a_files[tid], b_files[tid]) for tid in shared]
    field_summary = {}
    for field in FIELDS:
        rows = [p["fields"][field] for p in pair_scores]
        field_summary[field] = {
            "n_trajectories": len(rows),
            "exact_agreement_rate": sum(r["exact_agreement"] for r in rows) / len(rows),
            "mean_jaccard": sum(r["jaccard"] for r in rows) / len(rows),
        }

    pooled_a: list[int] = []
    pooled_b: list[int] = []
    for tid in shared:
        aa = json.loads(a_files[tid].read_text())
        bb = json.loads(b_files[tid].read_text())
        case = json.loads((SOURCE_CASES / f"{tid}.json").read_text())
        q_a = aa.get("questions", {})
        q_b = bb.get("questions", {})
        for field, kind in {
            "affected_claims": "claims",
            "affected_decisions": "decisions",
            "affected_assertions": "assertions",
        }.items():
            sa = set(_list_value(q_a, field)); sb = set(_list_value(q_b, field))
            for oid in sorted(case["objects"].get(kind, {})):
                pooled_a.append(int(oid in sa)); pooled_b.append(int(oid in sb))

    return {
        "schema": "prr-annotation-agreement-summary-1",
        "n_trajectories": len(shared),
        "trajectory_ids": shared,
        "fields": field_summary,
        "pooled_object_level": {
            "n_labels": len(pooled_a),
            "percent_agreement": sum(a == b for a, b in zip(pooled_a, pooled_b)) / len(pooled_a) if pooled_a else None,
            "cohen_kappa": _binary_kappa(pooled_a, pooled_b),
        },
        "per_trajectory": pair_scores,
    }


def adjudication_template(path_a: Path, path_b: Path) -> dict:
    a = json.loads(path_a.read_text()); b = json.loads(path_b.read_text())
    if a.get("trajectory_id") != b.get("trajectory_id"):
        raise ValueError("annotation files have different trajectory_id values")
    q_a = a.get("questions", {}); q_b = b.get("questions", {})
    disagreements = {}
    for field in FIELDS:
        va = sorted(set(_list_value(q_a, field)))
        vb = sorted(set(_list_value(q_b, field)))
        if va != vb:
            disagreements[field] = {
                "annotator_a": va,
                "annotator_b": vb,
                "adjudicated_value": None,
                "rationale": None,
            }
    return {
        "schema": "prr-adjudication-template-1",
        "trajectory_id": a["trajectory_id"],
        "instructions": [
            "Resolve only the disagreements shown below using the source packet and study protocol.",
            "Do not inspect system predictions while adjudicating.",
            "Record the adjudicated set and a brief rationale for every disagreement.",
        ],
        "disagreements": disagreements,
        "complete": False,
    }

def main(argv=None):
    p=argparse.ArgumentParser(description="Generate blind annotation packets, score pairs, aggregate a round, or prepare adjudication.")
    sp=p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("generate")
    s=sp.add_parser("score")
    s.add_argument("annotation_a", type=Path); s.add_argument("annotation_b", type=Path)
    s.add_argument("--out", type=Path)
    a=sp.add_parser("aggregate")
    a.add_argument("annotator_a_dir", type=Path); a.add_argument("annotator_b_dir", type=Path)
    a.add_argument("--out", type=Path)
    j=sp.add_parser("adjudicate-template")
    j.add_argument("annotation_a", type=Path); j.add_argument("annotation_b", type=Path)
    j.add_argument("--out", type=Path)
    args=p.parse_args(argv)
    if args.cmd == "generate": return generate_packets()
    if args.cmd == "score":
        result=score_pair(args.annotation_a,args.annotation_b)
    elif args.cmd == "aggregate":
        result=aggregate_dirs(args.annotator_a_dir,args.annotator_b_dir)
    else:
        result=adjudication_template(args.annotation_a,args.annotation_b)
    text=json.dumps(result,indent=2)+"\n"
    if args.out: args.out.write_text(text)
    else: print(text,end="")
    return 0

if __name__ == "__main__": raise SystemExit(main())
