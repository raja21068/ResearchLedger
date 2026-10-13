"""V5 Discovery Grounding.

Combines the user-provided corpus with targeted academic search, builds a novelty tree
and challenge→insight map, and performs a Level 1–4 well-established-solution check
BEFORE idea generation.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent))

from utils import ClaudeClient, load_json, save_json, save_markdown, log, print_banner
from step6_novelty import search_semantic_scholar, search_arxiv, search_openalex
from ideation_memory import select_relevant_memory, fundamental_failure_signatures


def solution_level_is_eligible(level) -> bool:
    try:
        return int(level) in {3, 4}
    except Exception:
        return False


def _norm_paper(row: dict, source: str) -> dict:
    return {
        "paper_id": row.get("paper_id") or row.get("paperId") or row.get("doi") or row.get("url") or row.get("title"),
        "title": row.get("title", ""),
        "year": row.get("year") or str(row.get("published", ""))[:4] or None,
        "venue": row.get("venue", ""),
        "abstract": (row.get("abstract") or row.get("summary") or "")[:1800],
        "url": row.get("url", ""),
        "source": source,
        "citation_count": row.get("citationCount") or row.get("cited_by_count") or 0,
    }


def _dedupe(rows: list[dict], max_n: int) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        title = " ".join(str(r.get("title", "")).lower().split())
        if not title or title in seen:
            continue
        seen.add(title)
        out.append(r)
        if len(out) >= max_n:
            break
    return out

def _norm_text(text: str) -> str:
    return " ".join(str(text or "").replace("“", '"').replace("”", '"').replace("’", "'").split()).lower()


def _validate_solution_evidence(field_map: dict, pool: list[dict], gaps: list[dict]) -> dict:
    """Enforce quote-or-zero and fail closed for omitted GAP-IDs."""
    by_title={_norm_text(p.get("title")):p for p in pool if p.get("title")}
    limitations=list(field_map.get("coverage_limitations",[]) or [])
    seen=set()
    cleaned=[]
    for row in field_map.get("gap_solution_checks",[]) or []:
        gid=str(row.get("gap_id", "")); seen.add(gid)
        valid=[]
        for ev in row.get("evidence",[]) or []:
            title=str(ev.get("paper_title", "")); quote=str(ev.get("quote", ""))
            paper=by_title.get(_norm_text(title))
            if not paper or not quote:
                continue
            abstract=_norm_text(paper.get("abstract", "")); q=_norm_text(quote)
            if q and q in abstract:
                valid.append({"paper_title":paper.get("title"),"quote":quote})
        row["evidence"]=valid
        row["evidence_titles"]=[x["paper_title"] for x in valid]
        try: level=int(row.get("level"))
        except Exception: level=0
        row["level"]=level
        if level in {1,2,3,4}:
            row["action"]="PROCEED" if level in {3,4} else "SWITCH"
        else:
            row["action"]="SWITCH"; row["confidence"]="LOW"
        if not valid:
            row["confidence"]="LOW"
            limitations.append(f"{gid or 'unknown gap'}: no exact abstract quote survived evidence validation; solution-level judgment is low confidence.")
        cleaned.append(row)
    for g in gaps:
        gid=str(g.get("gap_id", ""))
        if gid and gid not in seen:
            cleaned.append({"gap_id":gid,"level":0,"action":"SWITCH","confidence":"LOW","technical_core":"","evidence":[],"evidence_titles":[],"rationale":"Gap omitted by mapping model; fail closed."})
            limitations.append(f"{gid}: omitted from model solution checks; blocked by fail-closed policy.")
    field_map["gap_solution_checks"]=cleaned
    field_map["coverage_limitations"]=list(dict.fromkeys(limitations))
    return field_map


def _query_plan(client: ClaudeClient, gaps: list[dict], papers: list[dict], max_rounds: int, qpr: int, memory: list[dict]) -> dict:
    system = """You design literature-grounding searches for research ideation. The goal is NOT to support a preferred idea; it is to map the field broadly enough to identify unsolved problems and detect already-solved ones.
Return ONLY JSON.
Create diverse short academic search queries. Cover: canonical problem terms, competing mechanisms, adjacent-domain analogues, evaluation/benchmark terms, and recent terminology. Avoid cosmetic paraphrases.
Schema:
{"research_goal":"...","angle_tags":["..."],"rounds":[{"round":1,"queries":[{"query":"...","angle":"..."}]}]}
"""
    context = {
        "gaps": [{"gap_id":g.get("gap_id"),"type":g.get("gap_type"),"title":g.get("title") or g.get("description"),"evidence":g.get("evidence",[])[:3]} for g in gaps[:12]],
        "seed_papers": [{"title":p.get("title"),"year":p.get("year"),"method":p.get("method_name") or p.get("method",{}).get("name","")} for p in papers[:30]],
        "relevant_memory": memory,
        "max_rounds": max_rounds,
        "queries_per_round": qpr,
    }
    try:
        plan = client.ask_json(system, json.dumps(context, ensure_ascii=False)[:26000], temperature=0.0)
        rounds = plan.get("rounds", [])
        clean=[]
        for i in range(max_rounds):
            src = rounds[i] if i < len(rounds) else {}
            qs=[]
            for x in src.get("queries", [])[:qpr]:
                q = str(x.get("query", "")).strip()
                if q:
                    qs.append({"query":q,"angle":str(x.get("angle", "general"))})
            clean.append({"round":i+1,"queries":qs})
        plan["rounds"] = clean
        return plan
    except Exception as exc:
        log.warning(f"Discovery query planner degraded gracefully: {exc}")
        fallback=[]
        for g in gaps[: max_rounds*qpr]:
            q=str(g.get("title") or g.get("description") or "").strip()
            if q:
                fallback.append(q[:120])
        rounds=[]
        for i in range(max_rounds):
            subset=fallback[i*qpr:(i+1)*qpr]
            rounds.append({"round":i+1,"queries":[{"query":q,"angle":"gap"} for q in subset]})
        return {"research_goal":"Gap-driven discovery","angle_tags":["gap"],"rounds":rounds}


def _saturation_gate(client: ClaudeClient, goal: str, angle_tags: list[str], pool: list[dict], round_no: int, min_target: int) -> dict:
    system = """Act as a literature coverage auditor. Decide whether the discovery pool is sufficiently broad for research ideation. Do not stop merely because there are many papers. Stop only if the major problem/mechanism/evaluation/adjacent-domain angles are represented and no obvious high-value gap in coverage remains.
Return ONLY JSON: {"decision":"STOP|CONTINUE","covered_angles":["..."],"uncovered_angles":["..."],"reason":"..."}
"""
    compact=[{"title":p.get("title"),"year":p.get("year"),"abstract":p.get("abstract","")[:350],"source":p.get("source")} for p in pool[-35:]]
    try:
        out=client.ask_json(system, json.dumps({"goal":goal,"requested_angles":angle_tags,"round":round_no,"paper_count":len(pool),"minimum_target":min_target,"papers":compact}, ensure_ascii=False)[:30000], temperature=0.0)
        if out.get("decision") not in {"STOP","CONTINUE"}:
            out["decision"]="CONTINUE"
        if len(pool) < min_target:
            out["decision"]="CONTINUE"
            out["reason"]="Below configured minimum paper target. " + str(out.get("reason", ""))
        return out
    except Exception as exc:
        return {"decision":"STOP" if len(pool)>=min_target else "CONTINUE","covered_angles":[],"uncovered_angles":[],"reason":f"Deterministic fallback after saturation-auditor error: {exc}"}


def _build_map(client: ClaudeClient, gaps: list[dict], pool: list[dict], relevant_memory: list[dict], failures: list[str]) -> dict:
    system = """You are a senior research strategist. Build an evidence-grounded map BEFORE idea generation.

Tasks:
1) Build a novelty tree: Type 1=new task/problem; Type 2=new paradigm/pipeline/representation; Type 3=new mechanism/module; Type 4=incremental modification.
2) Build a challenge→insight tree mapping technical challenges to techniques/insights that address them.
3) For EACH supplied GAP-ID, run a well-established-solution check:
   Level 1: same task already has a good solution; action SWITCH.
   Level 2: same technical core is already well solved across domains; action SWITCH.
   Level 3: only limited/distant-domain solutions; action PROCEED.
   Level 4: no known good solution for the technical core; action PROCEED.
Do not manufacture novelty from missing retrieval. If evidence is thin, mark confidence LOW and explain the uncertainty.
4) Identify transfer opportunities and saturated areas.
5) Treat remembered FUNDAMENTAL failures as warnings, not truth; require current literature evidence before excluding a direction.

Every evidence item must cite a paper title present in the supplied pool and copy an exact short quote from the supplied abstract. If no abstract supports a judgment, return no evidence and LOW confidence. Return ONLY JSON:
{
 "novelty_tree":{"type1":[],"type2":[],"type3":[],"type4":[]},
 "challenge_insight_tree":[{"challenge":"...","insights":["..."],"paper_titles":["..."]}],
 "gap_solution_checks":[{"gap_id":"GAP-001","level":1,"action":"SWITCH|PROCEED","confidence":"HIGH|MEDIUM|LOW","technical_core":"...","evidence":[{"paper_title":"exact supplied title","quote":"exact short quote copied from that paper abstract"}],"rationale":"..."}],
 "transfer_opportunities":[{"from":"...","to":"...","why_non_obvious":"...","evidence_titles":["..."]}],
 "saturated_areas":[{"area":"...","why":"...","evidence_titles":["..."]}],
 "coverage_limitations":["..."]
}
"""
    data={
        "gaps":[{"gap_id":g.get("gap_id"),"gap_type":g.get("gap_type"),"description":g.get("description") or g.get("title"),"evidence":g.get("evidence",[])[:5]} for g in gaps],
        "papers":pool[:50],
        "relevant_prior_memory":relevant_memory,
        "remembered_fundamental_failures":failures[:12],
    }
    out=client.ask_json(system, json.dumps(data,ensure_ascii=False)[:58000], temperature=0.0)
    return _validate_solution_evidence(out, pool, gaps)


def generate_md(data: dict) -> str:
    cov=data.get("coverage",{})
    lines=["# V5 Discovery Grounding\n",f"Generated: {data.get('generated','')}\n",
           f"- Papers in grounded pool: **{cov.get('paper_count',0)}**",
           f"- Target: {cov.get('target_min')}–{cov.get('target_max')}",
           f"- Coverage status: **{cov.get('status','')}**",
           f"- Search rounds executed: {cov.get('rounds_run',0)}\n"]
    lines.append("## Well-established solution check\n")
    lines.append("| Gap | Level | Action | Confidence | Technical core |")
    lines.append("|---|---:|---|---|---|")
    for r in data.get("map",{}).get("gap_solution_checks",[]):
        lines.append(f"| {r.get('gap_id')} | {r.get('level')} | {r.get('action')} | {r.get('confidence')} | {r.get('technical_core','')} |")
    lines.append("\n## Challenge → Insight Tree\n")
    for r in data.get("map",{}).get("challenge_insight_tree",[]):
        lines.append(f"- **{r.get('challenge','')}**")
        for x in r.get("insights",[]): lines.append(f"  - {x}")
    lines.append("\n## Coverage limitations\n")
    for x in data.get("map",{}).get("coverage_limitations",[]): lines.append(f"- {x}")
    return "\n".join(lines)


def run_discovery_grounding(config: dict) -> dict:
    print_banner("STEP 4B: V5 LITERATURE GROUNDING + PROBLEM SELECTION")
    cfg=config["pipeline"]; out=Path(cfg["output_dir"])
    dcfg=config.get("discovery_grounding",{})
    if not dcfg.get("enabled",True):
        data={"generated":datetime.now().isoformat(),"enabled":False,"map":{"gap_solution_checks":[]},"papers":[]}
        save_json(data,str(out/"discovery_grounding.json")); return data

    corpus=load_json(str(out/"paper_corpus.json"))
    gap_data=load_json(str(out/"gap_analysis.json"))
    raw_papers=[p for p in corpus.get("papers",[]) if "_error" not in p]
    gaps=gap_data.get("gaps",[])
    local=[_norm_paper(p,"input_corpus") for p in raw_papers if p.get("title")]
    goal_text=" ".join([str(g.get("description") or g.get("title") or "") for g in gaps[:8]])
    relevant_memory=select_relevant_memory(config,goal_text) if config.get("idea_evolution",{}).get("use_ideation_memory",True) else []
    failures=fundamental_failure_signatures(config)

    client=ClaudeClient(config=config)
    max_rounds=int(dcfg.get("max_search_rounds",3)); qpr=int(dcfg.get("queries_per_round",3))
    target_min=int(dcfg.get("target_min_papers",30)); target_max=int(dcfg.get("target_max_papers",50))
    limit=int(dcfg.get("results_per_query",8))
    plan=_query_plan(client,gaps,raw_papers,max_rounds,qpr,relevant_memory)
    pool=_dedupe(local,target_max)
    round_logs=[]

    for r in plan.get("rounds",[])[:max_rounds]:
        if len(pool)>=target_max: break
        added=[]
        for qrow in r.get("queries",[])[:qpr]:
            q=qrow.get("query","")
            if not q: continue
            rows=[]
            if dcfg.get("semantic_scholar",True): rows += [_norm_paper(x,"semantic_scholar") for x in search_semantic_scholar(q,limit=limit)]
            if dcfg.get("arxiv",True): rows += [_norm_paper(x,"arxiv") for x in search_arxiv(q,max_results=limit)]
            if dcfg.get("openalex",True): rows += [_norm_paper(x,"openalex") for x in search_openalex(q,limit=limit)]
            before={" ".join(x.get("title","").lower().split()) for x in pool}
            for x in rows:
                key=" ".join(x.get("title","").lower().split())
                if key and key not in before:
                    added.append(x); before.add(key)
            pool=_dedupe(pool+added,target_max)
            time.sleep(0.15)
        gate=_saturation_gate(client,plan.get("research_goal",goal_text),plan.get("angle_tags",[]),pool,int(r.get("round",len(round_logs)+1)),target_min)
        round_logs.append({"round":r.get("round"),"queries":r.get("queries",[]),"new_unique":len(_dedupe(added,9999)),"pool_size":len(pool),"saturation":gate})
        if gate.get("decision")=="STOP" and len(pool)>=target_min: break

    status="SATURATED" if len(pool)>=target_min and round_logs and round_logs[-1]["saturation"].get("decision")=="STOP" else ("TARGET_REACHED_UNCERTAIN" if len(pool)>=target_min else "UNDER_TARGET")
    field_map=_build_map(client,gaps,pool,relevant_memory,failures)
    data={
        "generated":datetime.now().isoformat(),"enabled":True,
        "coverage":{"paper_count":len(pool),"target_min":target_min,"target_max":target_max,"status":status,"rounds_run":len(round_logs)},
        "query_plan":plan,"rounds":round_logs,"papers":pool,"map":field_map,
        "memory_used":relevant_memory,
    }
    save_json(data,str(out/"discovery_grounding.json"))
    save_markdown(generate_md(data),str(out/"discovery_grounding.md"))
    log.info(f"Discovery pool: {len(pool)} papers — {status}")
    return data


if __name__ == "__main__":
    from utils import load_config
    run_discovery_grounding(load_config())
