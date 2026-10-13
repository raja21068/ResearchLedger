"""V5 multi-track idea generation and evolution.

Up to three eligible research directions are generated from Level 3/4 gaps. Each track
runs N refinement iterations. Every iteration forces Innovator, Pragmatist, and Critic
variants before one is selected as the next seed. The champions are the ONLY ideas
handed to the adversarial Phase 10–14 survival loop.
"""
from __future__ import annotations
import copy, json
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent))

from utils import ClaudeClient, load_json, save_json, save_markdown, log, print_banner
from schema_validator import validate_json, validate_semantics
from ideation_memory import select_relevant_memory, fundamental_failure_signatures
from step4b_discovery_grounding import solution_level_is_eligible


def eligible_gap_ids(discovery: dict, require_level34: bool = True) -> set[str]:
    rows=discovery.get("map",{}).get("gap_solution_checks",[])
    if not require_level34:
        return {str(r.get("gap_id")) for r in rows if r.get("gap_id")}
    return {str(r.get("gap_id")) for r in rows if r.get("gap_id") and solution_level_is_eligible(r.get("level")) and r.get("action")=="PROCEED"}


def _idea_contract() -> str:
    return r'''Each idea object MUST contain:
{
 "idea_id":"IDEA-001","source_gap":"GAP-001","gap_type":"VOID","title":"...",
 "research_direction":"...",
 "hypothesis":{"statement":"If X then Y because Z","null_hypothesis":"...","expected_direction":"positive|negative|diagnostic"},
 "method_sketch":{"approach":"...","key_components":[],"baselines":[],"ablations":[]},
 "experiment_design":{"datasets":[],"metrics":[],"evaluation_protocol":"...","minimum_viable_experiment":"..."},
 "feasibility":{"compute_estimate":"...","data_requirements":"...","implementation_complexity":"days|weeks|months","dependencies":[]},
 "expected_outcomes":{"if_positive":"...","if_negative":"...","either_way_value":"..."},
 "contribution_type":"empirical|method|theoretical|diagnostic|benchmark|reproduction",
 "risk_assessment":{"risk_level":"LOW|MEDIUM|HIGH","main_risk":"...","mitigation":"...","reviewer_objection":"..."},
 "positioning":{"closest_work":"...","differentiation":"...","target_venue":"...","contribution_sentence":"..."},
 "scoring":{"gap_importance":1,"scientific_rigor":1,"feasibility":1,"either_way_value":1,"novelty_potential":1,"weighted_score":1.0}
}'''


def _initial_directions(client: ClaudeClient, gaps: list[dict], discovery: dict, eligible: set[str], n: int, memory: list[dict], failures: list[str]) -> list[dict]:
    system=f"""You are a senior research ideation panel. Generate up to {n} FUNDAMENTALLY DIFFERENT research directions, each tied to an eligible GAP-ID that passed the Level 3/4 well-established-solution check.

Rules:
- Problem selection > solution decoration.
- Prefer new failure cases, new scientific questions, new mechanisms, or non-obvious cross-domain transfer over benchmark tuning.
- Do not generate an idea from Level 1/2 gaps.
- Do not repeat remembered fundamental failures unless current literature provides a materially different mechanism.
- At least one direction should be diagnostic/benchmark/empirical when scientifically appropriate.
- A mere A→B concatenation is not a contribution.
- Every idea must be testable, feasible, and state the value of a negative result.

{_idea_contract()}
Return ONLY JSON: {{"ideas":[...],"rejected_directions":[{{"gap_id":"...","reason":"..."}}]}}
"""
    context={
      "eligible_gap_ids":sorted(eligible),
      "gaps":[g for g in gaps if g.get("gap_id") in eligible],
      "discovery_map":discovery.get("map",{}),
      "relevant_memory":memory,
      "remembered_fundamental_failures":failures[:12],
    }
    out=client.ask_json(system,json.dumps(context,ensure_ascii=False)[:56000],temperature=0.35)
    ideas=[]
    for i,idea in enumerate(out.get("ideas",[])[:n],1):
        if idea.get("source_gap") not in eligible:
            continue
        idea["idea_id"]=f"IDEA-{i:03d}"
        ideas.append(idea)
    return ideas


def _refine_round(client: ClaudeClient, current: dict, discovery: dict, iteration: int, failures: list[str]) -> dict:
    system=f"""Run one adversarial EVOLUTION round for a research idea. This is NOT the final novelty attack loop; it is pre-attack idea evolution.

All three personas must independently propose a COMPLETE revised idea:
- Innovator: maximize non-obvious novelty; may pivot mechanism.
- Pragmatist: maximize executable rigor and clean validation.
- Critic: maximize scientific insight, falsifiability, and reviewer defensibility.

First evaluate the current seed on novelty potential, feasibility, impact, alignment, coherence, and risk. Then produce all 3 persona variants. Finally select exactly one variant as the next seed using evidence, not personality preference.
If the current mechanism is a dead end, the winning variant MUST pivot rather than cosmetically patch it.
Do not erase source_gap or hypothesis/null-hypothesis traceability.

{_idea_contract()}
Return ONLY JSON:
{{
 "iteration":{iteration},
 "evaluation":{{"novelty":"...","feasibility":"...","impact":"...","alignment":"...","coherence":"...","main_failure_mode":"..."}},
 "variants":{{"innovator":{{...idea...}},"pragmatist":{{...idea...}},"critic":{{...idea...}}}},
 "selected_persona":"innovator|pragmatist|critic",
 "selection_reason":"...",
 "selected_idea":{{...complete idea...}},
 "pivoted":false
}}
"""
    context={"current_idea":current,"discovery_map":discovery.get("map",{}),"remembered_fundamental_failures":failures[:10]}
    result=client.ask_json(system,json.dumps(context,ensure_ascii=False)[:50000],temperature=0.25)
    selected=result.get("selected_idea")
    if not isinstance(selected,dict) or not selected:
        raise ValueError("Evolution round returned no selected_idea")
    selected["idea_id"]=current.get("idea_id")
    selected["source_gap"]=current.get("source_gap")
    if not selected.get("gap_type"): selected["gap_type"]=current.get("gap_type")
    h=selected.get("hypothesis",{})
    if not h.get("statement") or not h.get("null_hypothesis"):
        raise ValueError("Evolution selected idea lost hypothesis/null hypothesis")
    return result


def _weighted_score(idea: dict) -> float:
    s=idea.get("scoring",{})
    try:
        return round(0.30*float(s.get("gap_importance",0))+0.25*float(s.get("scientific_rigor",0))+0.20*float(s.get("feasibility",0))+0.15*float(s.get("either_way_value",0))+0.10*float(s.get("novelty_potential",0)),3)
    except Exception:
        return 0.0


def generate_md(data: dict) -> str:
    lines=["# V5 Evolved Idea Champions\n",f"Generated: {data.get('generated','')}\n",
           f"- Eligible gaps: {data.get('eligible_gap_count',0)}",
           f"- Tracks started: {data.get('tracks_started',0)}",
           f"- Evolution iterations per track: {data.get('iterations',0)}",
           f"- Champions entering adversarial zone: {len(data.get('ideas',[]))}\n"]
    for idea in data.get("ideas",[]):
        lines.append(f"## {idea.get('idea_id')} — {idea.get('title','')}")
        lines.append(f"- Source gap: {idea.get('source_gap')}")
        lines.append(f"- Direction: {idea.get('research_direction','')}")
        lines.append(f"- Hypothesis: {idea.get('hypothesis',{}).get('statement','')}")
        lines.append(f"- Contribution: {idea.get('positioning',{}).get('contribution_sentence','')}")
        lines.append(f"- Evolution winner sequence: {' → '.join(idea.get('_evolution_personas',[]))}\n")
    return "\n".join(lines)


def run_idea_evolution(config: dict) -> dict:
    print_banner("STEP 5: V5 MULTI-PERSONA IDEA EVOLUTION")
    out=Path(config["pipeline"]["output_dir"])
    ecfg=config.get("idea_evolution",{})
    discovery=load_json(str(out/"discovery_grounding.json"))
    gaps_data=load_json(str(out/"gap_analysis.json")); gaps=gaps_data.get("gaps",[])
    dcfg=config.get("discovery_grounding",{})
    if dcfg.get("fail_closed_under_min_papers", True):
        cov=discovery.get("coverage",{})
        if int(cov.get("paper_count",0)) < int(cov.get("target_min", dcfg.get("target_min_papers",30))):
            data={"generated":datetime.now().isoformat(),"ideas":[],"eligible_gap_count":0,"tracks_started":0,"iterations":int(ecfg.get("iterations",3)),"eliminated_ideas":[],"traceability_matrix":[],"note":"Discovery pool is below the configured minimum; ideation failed closed."}
            save_json(data,str(out/"idea_report.json")); save_json({"tracks":[]},str(out/"evolution_trace.json")); save_markdown(generate_md(data),str(out/"idea_report.md")); return data
    eligible=eligible_gap_ids(discovery,dcfg.get("require_solution_level_3_or_4",True))

    if not eligible and dcfg.get("fail_closed_if_no_eligible_gap",True):
        data={"generated":datetime.now().isoformat(),"ideas":[],"eligible_gap_count":0,"tracks_started":0,"iterations":int(ecfg.get("iterations",3)),"eliminated_ideas":[],"traceability_matrix":[],"note":"No Level 3/4 gap survived problem selection; ideation failed closed."}
        save_json(data,str(out/"idea_report.json")); save_json({"tracks":[]},str(out/"evolution_trace.json")); save_markdown(generate_md(data),str(out/"idea_report.md")); return data

    goal=" ".join(str(g.get("description") or g.get("title") or "") for g in gaps if g.get("gap_id") in eligible)
    memory=select_relevant_memory(config,goal) if ecfg.get("use_ideation_memory",True) else []
    failures=fundamental_failure_signatures(config)
    client=ClaudeClient(config=config)
    n=int(ecfg.get("directions",3)); iterations=int(ecfg.get("iterations",3))
    seeds=_initial_directions(client,gaps,discovery,eligible,n,memory,failures)
    tracks=[]; champions=[]

    for seed in seeds:
        current=copy.deepcopy(seed); rounds=[]; persona_seq=[]
        for it in range(1,iterations+1):
            rr=_refine_round(client,current,discovery,it,failures)
            rounds.append(rr)
            persona_seq.append(rr.get("selected_persona","?"))
            current=copy.deepcopy(rr["selected_idea"])
            current["idea_id"]=seed["idea_id"]
            current["source_gap"]=seed["source_gap"]
        current.setdefault("scoring",{})["weighted_score"]=_weighted_score(current)
        current["_evolution_personas"]=persona_seq
        current["_evolution_iterations"]=iterations
        champions.append(current)
        tracks.append({"idea_id":seed["idea_id"],"source_gap":seed["source_gap"],"initial_idea":seed,"rounds":rounds,"champion":current})

    trace=[]
    gap_by_id={g.get("gap_id"):g for g in gaps}
    for idea in champions:
        g=gap_by_id.get(idea.get("source_gap"),{})
        trace.append({"idea_id":idea.get("idea_id"),"gap_id":idea.get("source_gap"),"gap_type":idea.get("gap_type") or g.get("gap_type"),"gap_priority":g.get("scoring",{}).get("priority_score")})
    data={
        "generated":datetime.now().isoformat(),"total_gaps_analyzed":len(gaps),"total_ideas_generated":len(seeds),"total_ideas_surviving":len(champions),
        "eligible_gap_count":len(eligible),"tracks_started":len(seeds),"iterations":iterations,
        "ideas":champions,"eliminated_ideas":[],"traceability_matrix":trace,
        "v4_policy":{"level1_2_never_enter_ideation":True,"three_personas_each_iteration":True,"champions_only_enter_attack_loop":True}
    }
    issues=validate_semantics("idea_report",data)
    if issues: raise ValueError("V5 idea semantic validation failed: "+" | ".join(issues))
    schema=Path(__file__).resolve().parent.parent/"schemas"/"idea_report.schema.json"
    validate_json(data,schema)
    save_json(data,str(out/"idea_report.json")); save_json({"generated":datetime.now().isoformat(),"tracks":tracks},str(out/"evolution_trace.json")); save_markdown(generate_md(data),str(out/"idea_report.md"))
    log.info(f"Evolved {len(champions)} champion ideas from {len(eligible)} eligible gaps")
    return data


if __name__ == "__main__":
    from utils import load_config
    run_idea_evolution(load_config())
