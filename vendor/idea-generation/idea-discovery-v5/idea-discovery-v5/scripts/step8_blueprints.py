"""V5 — turn FINAL GREENLIGHT survivors into full-study methodology blueprints, preserving survivor ELO rank when available."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import ClaudeClient, load_config, load_json, save_json, save_markdown, print_banner

SYSTEM_PROMPT = """You are a Research Architect. Build a concrete methodology blueprint for each supplied research idea that survived the iterative Phase 10–13 attack loop.
The research question/hypothesis drives the method, never fashion. Make every design choice traceable to the hypothesis.
For AI/computer-science work, explicitly specify datasets, baselines, ablations, statistical testing, robustness checks, compute budget, reproducibility artifacts, leakage controls, and failure criteria. For other domains, adapt appropriately. Do not invent dataset access or ethics approval.

Return ONLY JSON:
{
 "blueprints":[{
   "idea_id":"IDEA-001",
   "decision_inherited":"GREENLIGHT",
   "research_question":"...",
   "design_type":"...",
   "methodological_rationale":"...",
   "data_strategy":{"sources":[],"sampling_or_selection":"...","leakage_controls":[]},
   "analysis_plan":{"primary_analysis":[],"baselines":[],"ablations":[],"statistical_tests":[],"robustness_checks":[]},
   "success_failure_criteria":{"primary_success":"...","null_or_failure":"...","stopping_rule":"..."},
   "validity":{"internal":[],"external":[],"construct":[],"reproducibility":[]},
   "ethics_and_governance":{"human_subjects":"yes|no|unclear","irb_note":"...","data_privacy":[]},
   "preregistration":"recommended|optional|not_applicable",
   "minimum_viable_study":"...",
   "full_study":"...",
   "artifacts_to_release":[],
   "known_limitations":[]
 }]
}
"""


def generate_md(data: dict) -> str:
    lines=["# Research Methodology Blueprints (V5)\n", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    for b in data.get("blueprints", []):
        lines.append(f"## {b.get('idea_id','?')} — {b.get('design_type','')} [{b.get('decision_inherited','')}]\n")
        lines.append(f"**Research question:** {b.get('research_question','')}\n")
        lines.append(f"**Rationale:** {b.get('methodological_rationale','')}\n")
        lines.append(f"**Minimum viable study:** {b.get('minimum_viable_study','')}\n")
        sf=b.get('success_failure_criteria',{})
        lines.append(f"**Success criterion:** {sf.get('primary_success','')}  ")
        lines.append(f"**Null/failure criterion:** {sf.get('null_or_failure','')}\n")
        ap=b.get('analysis_plan',{})
        for title,key in [("Baselines","baselines"),("Ablations","ablations"),("Statistical tests","statistical_tests"),("Robustness checks","robustness_checks")]:
            vals=ap.get(key,[])
            if vals:
                lines.append(f"### {title}")
                lines.extend(f"- {x}" for x in vals)
        lines.append("")
    return "\n".join(lines)


def run_blueprints(config: dict) -> dict:
    print_banner("STEP 9: V5 Research Architecture Blueprints")
    out=Path(config["pipeline"]["output_dir"])
    # V5: full-study blueprints are generated only for FINAL GREENLIGHT ideas
    # that survived the falsification/MVE evidence zone. Legacy V4 fallback remains.
    loop_path = out/"falsification_summary.json"
    if not loop_path.exists():
        loop_path = out/"attack_loop_summary.json"
    if loop_path.exists():
        loop_data = load_json(str(loop_path))
        survivors = []
        for item in loop_data.get("ideas", []):
            if item.get("final_decision") == "GREENLIGHT" and isinstance(item.get("final_idea"), dict):
                survivors.append(dict(item["final_idea"], decision_inherited="GREENLIGHT",
                                      attack_rounds=item.get("literature_attack_rounds", item.get("rounds_run", 0)),
                                      falsification_rounds=item.get("rounds_run", 0) if "mve_evidence_present" in item else 0))
        elo_path = out/"survivor_elo.json"
        if elo_path.exists():
            elo_data = load_json(str(elo_path))
            elo_by_id = {r.get("idea_id"): r for r in elo_data.get("ranking", [])}
            for idea in survivors:
                row = elo_by_id.get(idea.get("idea_id"), {})
                idea["survivor_elo_rank"] = row.get("rank")
                idea["survivor_elo_rating"] = row.get("rating")
            survivors.sort(key=lambda x: x.get("survivor_elo_rank") or 999)
    else:
        # Backward-compatible fallback for legacy V3 artifacts.
        ideas=load_json(str(out/"idea_report.json")).get("ideas",[])
        gates=load_json(str(out/"adversarial_gate.json")).get("gates",[])
        decision={g.get("idea_id"):g.get("decision") for g in gates}
        survivors=[dict(i, decision_inherited=decision.get(i.get("idea_id"))) for i in ideas if decision.get(i.get("idea_id")) == "GREENLIGHT"]
    if not survivors:
        data={"generated":datetime.now().isoformat(),"blueprints":[],"note":"No ideas achieved FINAL GREENLIGHT after literature/reviewer attacks and V5 falsification/MVE evidence verification."}
    else:
        client=ClaudeClient(config=config)
        data=client.ask_json(SYSTEM_PROMPT, "Create blueprints for:\n"+json.dumps(survivors,ensure_ascii=False)[:50000])
        data["generated"]=datetime.now().isoformat()
    save_json(data,str(out/"research_blueprints.json"))
    save_markdown(generate_md(data),str(out/"research_blueprints.md"))
    return data

if __name__ == "__main__":
    run_blueprints(load_config())
