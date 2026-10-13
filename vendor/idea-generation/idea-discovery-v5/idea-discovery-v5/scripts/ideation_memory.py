"""V5 ideation memory: lightweight cross-run memory for feasible directions and dead ends."""
from __future__ import annotations
import json, re
from pathlib import Path
from datetime import datetime


def _tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]+", (text or "").lower()) if len(x) > 2}


def memory_path(config: dict) -> Path:
    raw = config.get("ideation_memory", {}).get("path", "memory/ideation_memory.json")
    return Path(raw)


def load_memory(config: dict) -> dict:
    path = memory_path(config)
    if not path.exists():
        return {"version": "5.0.0", "entries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("entries", []), list):
            raise ValueError("invalid memory structure")
        return data
    except Exception:
        return {"version": "5.0.0", "entries": []}


def select_relevant_memory(config: dict, query_text: str) -> list[dict]:
    """Select top-k entries by transparent token overlap, avoiding hidden semantic magic."""
    mem = load_memory(config)
    q = _tokens(query_text)
    scored = []
    for entry in mem.get("entries", []):
        hay = " ".join([
            str(entry.get("title", "")), str(entry.get("summary", "")),
            " ".join(entry.get("retrieval_tags", []) or []),
        ])
        t = _tokens(hay)
        overlap = len(q & t) / max(1, len(q | t))
        if overlap > 0:
            scored.append((overlap, entry))
    scored.sort(key=lambda x: (x[0], x[1].get("updated", "")), reverse=True)
    k = int(config.get("ideation_memory", {}).get("top_k_relevant", 2))
    return [dict(e, _relevance=round(s, 4)) for s, e in scored[:k]]


def fundamental_failure_signatures(config: dict) -> list[str]:
    mem = load_memory(config)
    out = []
    for e in mem.get("entries", []):
        if e.get("status") == "UNSUCCESSFUL" and e.get("failure_class") == "FUNDAMENTAL":
            out.extend([e.get("title", ""), e.get("summary", "")])
            out.extend(e.get("retrieval_tags", []) or [])
    return [x for x in out if str(x).strip()]


def update_memory(config: dict, attack_summary: dict, elo_summary: dict | None = None) -> dict:
    cfg = config.get("ideation_memory", {})
    if not cfg.get("enabled", True):
        return load_memory(config)
    path = memory_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    mem = load_memory(config)
    entries = mem.setdefault("entries", [])
    elo_by_id = {}
    if elo_summary:
        elo_by_id = {x.get("idea_id"): x for x in elo_summary.get("ranking", [])}

    now = datetime.now().isoformat()
    for item in attack_summary.get("ideas", []):
        iid = item.get("idea_id")
        final_idea = item.get("final_idea") or {}
        source = final_idea if final_idea else {"title": item.get("final_title") or item.get("original_title", "")}
        decision = item.get("final_decision", "")
        existing = next((e for e in entries if e.get("idea_id") == iid), None)
        if existing is None:
            existing = {"idea_id": iid, "created": now}
            entries.append(existing)
        existing.update({
            "updated": now,
            "title": source.get("title", ""),
            "summary": source.get("positioning", {}).get("contribution_sentence", "") or source.get("method_sketch", {}).get("approach", ""),
            "source_gap": source.get("source_gap", ""),
            "status": ("FEASIBLE" if decision == "GREENLIGHT" else ("READY_FOR_MVE" if decision == "READY_FOR_MVE" else ("EVIDENCE_REVISION" if decision == "REVISE_EVIDENCE" else "UNSUCCESSFUL"))),
            "failure_class": None if decision in {"GREENLIGHT","READY_FOR_MVE","REVISE_EVIDENCE"} else (
                "FUNDAMENTAL" if any(k in (" ".join(item.get("final_blockers", [])) + " " + str(item.get("reason", ""))).lower() for k in ["not novel", "collision", "already", "fatal", "contradicted"]) else "IMPLEMENTATION_OR_EVIDENCE"
            ),
            "final_decision": decision,
            "attack_rounds": item.get("literature_attack_rounds", item.get("rounds_run", 0)),
            "falsification_rounds": item.get("rounds_run", 0) if "mve_evidence_present" in item else 0,
            "retrieval_tags": list(dict.fromkeys([
                str(source.get("gap_type", "")), str(source.get("contribution_type", "")),
                *[str(x) for x in source.get("method_sketch", {}).get("key_components", [])[:5]],
            ])),
        })
        if iid in elo_by_id:
            existing["elo"] = elo_by_id[iid].get("rating")
            existing["elo_rank"] = elo_by_id[iid].get("rank")

    max_entries = int(cfg.get("max_entries", 100))
    entries.sort(key=lambda e: e.get("updated", ""), reverse=True)
    mem["entries"] = entries[:max_entries]
    mem["version"] = "5.0.0"
    mem["updated"] = now
    path.write_text(json.dumps(mem, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return mem
