"""Final report compiler for Idea Discovery V5."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils import load_config, load_json, save_json, save_markdown, log, print_banner


def _load(path: Path, default):
    try: return load_json(str(path)) if path.exists() else default
    except Exception: return default


def _novelty_verdict(v: dict) -> str:
    return v.get("consensus",{}).get("verdict") or v.get("assessment",{}).get("overall_assessment",{}).get("verdict") or v.get("overall_assessment",{}).get("verdict") or "UNKNOWN"


def _novelty_score(v: dict):
    return v.get("consensus",{}).get("novelty_score") or v.get("assessment",{}).get("overall_assessment",{}).get("novelty_score") or v.get("overall_assessment",{}).get("novelty_score") or "?"


def compile_final_report(config: dict) -> str:
    print_banner("STEP 11: V5 FINAL REPORT COMPILATION")
    out=Path(config["pipeline"]["output_dir"])
    corpus=_load(out/"paper_corpus.json",{"papers":[]}); source=_load(out/"source_verification.json",{})
    space=_load(out/"research_space_map.json",{}); conflicts=_load(out/"conflict_report.json",{}); gaps=_load(out/"gap_analysis.json",{})
    discovery=_load(out/"discovery_grounding.json",{}); evolution=_load(out/"evolution_trace.json",{})
    ideas=_load(out/"final_idea_report.json",{}) or _load(out/"idea_report.json",{})
    novelty=_load(out/"novelty_report.json",{}); gate=_load(out/"adversarial_gate.json",{}); attack_loop=_load(out/"attack_loop_summary.json",{})
    falsification=_load(out/"falsification_summary.json",{}); elo=_load(out/"survivor_elo.json",{}); blueprints=_load(out/"research_blueprints.json",{})

    papers=[p for p in corpus.get("papers",[]) if "_error" not in p]; idea_list=ideas.get("ideas",[]); gap_list=gaps.get("gaps",[])
    nov_by_id={v.get("idea_id"):v for v in novelty.get("verifications",[])}; gate_by_id={g.get("idea_id"):g for g in gate.get("gates",[])}; bp_by_id={b.get("idea_id"):b for b in blueprints.get("blueprints",[])}
    elo_by_id={r.get("idea_id"):r for r in elo.get("ranking",[])}
    fals_by_id={x.get("idea_id"):x for x in falsification.get("ideas",[])}
    final_idea_by_id={x.get("idea_id"):x.get("final_idea") for x in falsification.get("ideas",[]) if isinstance(x.get("final_idea"),dict)}
    candidates=[]; ready_for_mve=[]; evidence_revision=[]
    for idea in idea_list:
        iid=idea.get("idea_id"); nv=nov_by_id.get(iid,{}); g=gate_by_id.get(iid,{}); fx=fals_by_id.get(iid,{})
        current=final_idea_by_id.get(iid) or idea
        status=fx.get("final_decision") if fx else (("GREENLIGHT" if g.get("decision")=="GREENLIGHT" else "UNKNOWN") if g else "UNKNOWN")
        record={"idea":current,"novelty":nv,"gate":g,"falsification":fx,"blueprint":bp_by_id.get(iid),"elo":elo_by_id.get(iid,{})}
        if status=="GREENLIGHT": candidates.append(record)
        elif status=="READY_FOR_MVE": ready_for_mve.append(record)
        elif status=="REVISE_EVIDENCE": evidence_revision.append(record)
    candidates.sort(key=lambda x:(x["elo"].get("rank") or 999, -float(x["idea"].get("scoring",{}).get("weighted_score",0) or 0)))

    ss=source.get("summary",{}); ns=novelty.get("summary",{}); ga=gate.get("portfolio_assessment",{})
    high_gaps=[g for g in gap_list if g.get("scoring",{}).get("priority_score",0)>=18]; high_conflicts=[c for c in conflicts.get("conflicts",[]) if c.get("severity")=="HIGH"]
    dcv=discovery.get("coverage",{}); solution_checks=discovery.get("map",{}).get("gap_solution_checks",[])
    eligible=sum(1 for x in solution_checks if x.get("action")=="PROCEED" and x.get("level") in {3,4})

    lines=["# Idea Discovery V5 — Falsification-Gated Research Agenda\n",f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ","**Pipeline:** V5.0.0 — grounded discovery + multi-persona evolution + literature/reviewer attacks + empirical falsification + final-survivor ELO\n","---","## Executive summary\n","| Stage | Result |","|---|---|"]
    rows=[
      ("Papers ingested",f"{len(papers)} ({corpus.get('failed',0)} failed)"),
      ("Source verification",f"S2 verified {ss.get('S2_VERIFIED',0)}, Crossref verified {ss.get('VERIFIED',0)}, unverified {ss.get('UNVERIFIED',0)}, DOI problems {ss.get('DOI_MISMATCH',0)+ss.get('INVALID_DOI',0)}"),
      ("Discovery grounding",f"{dcv.get('paper_count',0)} papers; {dcv.get('status','UNKNOWN')}"),
      ("Problem-selection gate",f"{eligible} Level 3/4 gaps allowed forward; {max(0,len(solution_checks)-eligible)} switched/blocked"),
      ("Method / problem clusters",f"{len(space.get('method_clusters',[]))} / {len(space.get('problem_clusters',[]))}"),
      ("Conflicts",f"{len(conflicts.get('conflicts',[]))} ({len(high_conflicts)} high severity)"),
      ("Research gaps",f"{len(gap_list)} ({len(high_gaps)} high priority)"),
      ("Evolution tracks",f"{len(evolution.get('tracks',[]))} tracks × {config.get('idea_evolution',{}).get('iterations',3)} iterations"),
      ("Champion ideas entering attacks",str(len(idea_list))),
      ("Final-loop novelty status",f"PROCEED {ns.get('proceed',0)}, PIVOT {ns.get('pivot',0)}, ABANDON {ns.get('abandon',0)}"),
      ("Literature/reviewer survival",f"provisional GREENLIGHT {attack_loop.get('summary',{}).get('greenlight',ga.get('greenlight_count',0))}, KILL {attack_loop.get('summary',{}).get('kill',ga.get('kill_count',0))}"),
      ("V5 falsification",f"FINAL GREENLIGHT {falsification.get('summary',{}).get('greenlight',0)}, READY_FOR_MVE {falsification.get('summary',{}).get('ready_for_mve',0)}, REVISE {falsification.get('summary',{}).get('revise',0)}, KILL {falsification.get('summary',{}).get('kill',0)}"),
      ("Final-survivor ELO entrants",str(len(elo.get('ranking',[])))),
      ("Methodology blueprints",str(len(blueprints.get('blueprints',[])))),
      ("Actionable candidates",f"**{len(candidates)}**"),
    ]
    lines.extend(f"| {a} | {b} |" for a,b in rows)

    lines += ["\n---","## Recommended research agenda\n"]
    if not candidates: lines.append("No idea has FINAL GREENLIGHT yet. Literature/reviewer survival alone is insufficient in V5; run the required MVE evidence protocol for READY_FOR_MVE ideas or revise inconclusive evidence.\n")
    for rank,item in enumerate(candidates,1):
        idea,nv,g,fx,bp,er=item["idea"],item["novelty"],item["gate"],item["falsification"],item["blueprint"],item["elo"]
        lines.append(f"### {rank}. {idea.get('idea_id','?')}: {idea.get('title','')}")
        if er: lines.append(f"- **Survivor ELO:** rank {er.get('rank')} · rating {er.get('rating')} · mean comparison {er.get('mean_composite')}")
        lines.append(f"- **Final decision:** {fx.get('final_decision','GREENLIGHT')}")
        lines.append(f"- **Literature attack decision:** {g.get('decision','NOVELTY_ONLY')}")
        if fx.get("evidence_assessment"): lines.append(f"- **MVE evidence verdict:** {fx.get('evidence_assessment',{}).get('verdict','')} ({fx.get('evidence_assessment',{}).get('evidence_quality','')})")
        lines.append(f"- **Novelty:** {_novelty_verdict(nv)} ({_novelty_score(nv)}/10)")
        lines.append(f"- **Source gap:** {idea.get('source_gap','')} ({idea.get('gap_type','')})")
        lines.append(f"- **Hypothesis:** {idea.get('hypothesis',{}).get('statement','')}")
        lines.append(f"- **Intellectual contribution:** {nv.get('consensus',{}).get('key_differentiator') or nv.get('overall_assessment',{}).get('key_differentiator','')}")
        lines.append(f"- **Minimum experiment:** {idea.get('experiment_design',{}).get('minimum_viable_experiment','')}")
        if g: lines.append(f"- **Strongest counterargument:** {g.get('strongest_counterargument','')}")
        if bp:
            lines.append(f"- **Research design:** {bp.get('design_type','')}")
            lines.append(f"- **Success criterion:** {bp.get('success_failure_criteria',{}).get('primary_success','')}")
        lines.append("")

    lines += ["---","## MVE queue — literature-surviving ideas not yet empirically greenlit\n"]
    if not ready_for_mve:
        lines.append("No ideas are currently waiting for MVE evidence.\n")
    for item in ready_for_mve:
        idea=item["idea"]; fx=item["falsification"]
        lines.append(f"### {idea.get('idea_id')}: {idea.get('title','')} — READY_FOR_MVE")
        lines.append(f"- **Reason:** {fx.get('reason','')}")
        proto=(fx.get('history') or [{}])[-1].get('mve_protocol',{})
        if proto:
            lines.append(f"- **MVE objective:** {proto.get('objective','')}")
            lines.append(f"- **Falsification rule:** {proto.get('falsification_rule','')}")
        lines.append(f"- **Evidence file:** `output/mve_evidence/{idea.get('idea_id')}.json`")
        lines.append("")
    if evidence_revision:
        lines += ["### Evidence needing revision"]
        for item in evidence_revision:
            lines.append(f"- **{item['idea'].get('idea_id')}**: {item['falsification'].get('reason','')}")
        lines.append("")

    lines += ["---","## Problem-selection audit\n","| Gap | Solution level | Action | Confidence | Technical core |","|---|---:|---|---|---|"]
    for r in solution_checks: lines.append(f"| {r.get('gap_id')} | {r.get('level')} | {r.get('action')} | {r.get('confidence')} | {r.get('technical_core','')} |")

    if high_conflicts:
        lines += ["\n---","## High-severity unresolved conflicts\n"]
        for c in high_conflicts: lines.append(f"- **{c.get('conflict_id','')}**: {c.get('resolution_path') or c.get('description','')}")

    lines += ["\n---","## Gap inventory\n","| Rank | Gap | Type | Title | Priority |","|---:|---|---|---|---:|"]
    for rank,gap in enumerate(sorted(gap_list,key=lambda g:g.get("scoring",{}).get("priority_score",0),reverse=True),1):
        lines.append(f"| {rank} | {gap.get('gap_id','')} | {gap.get('gap_type') or gap.get('type','')} | {gap.get('title') or gap.get('description','')} | {gap.get('scoring',{}).get('priority_score',0)}/27 |")

    lines += ["\n---","## Audit artifacts\n",
      "- `discovery_grounding.json/.md` — 30–50-paper target, coverage rounds, novelty tree, challenge→insight tree, and Level 1–4 solution checks.",
      "- `evolution_trace.json` — all Innovator/Pragmatist/Critic variants and the selected seed for every evolution round.",
      "- `idea_report.json` — evolved track champions entering the adversarial zone.",
      "- `attack_loop/IDEA-*/round_*/` — Phase 10 scorecard, Phase 11 destructive novelty search, Phase 12 competitor matrix, Phase 13 reviewer attack, Phase 14 revision/pivot.",
      "- `falsification/IDEA-*/round_*/` — hypothesis contract, Occam/counterexample attack, blind verifier, MVE protocol, and evidence ledger.",
      "- `falsification_summary.json/.md` — FINAL GREENLIGHT / READY_FOR_MVE / evidence-revision outcomes.",
      "- `output/mve_evidence/IDEA-xxx.json` — user-supplied executed MVE evidence; absence cannot produce GREENLIGHT.",
      "- `survivor_elo.json/.md` — relative ranking of FINAL GREENLIGHT survivors only.",
      "- `research_blueprints.json/.md` — execution plans for surviving ideas.",
      "- `memory/ideation_memory.json` — cross-run feasible directions and classified dead ends.",
      "- `dashboard.html` and `SESSION.md` — interactive and portable views.\n"]

    report="\n".join(lines); save_markdown(report,str(out/"FINAL_REPORT.md"))
    compact={"generated":datetime.now().isoformat(),"pipeline_version":"5.0.0","papers":len(papers),"discovery_papers":dcv.get("paper_count",0),"eligible_gaps":eligible,"gaps":len(gap_list),"ideas":len(idea_list),"actionable":len(candidates),"ready_for_mve":len(ready_for_mve),"evidence_revision":len(evidence_revision),"top_ideas":[{"idea_id":x["idea"].get("idea_id"),"title":x["idea"].get("title"),"elo_rank":x["elo"].get("rank"),"decision":x["falsification"].get("final_decision","GREENLIGHT"),"novelty":_novelty_verdict(x["novelty"])} for x in candidates[:10]]}
    save_json(compact,str(out/"final_report_summary.json")); log.info(f"V5 final report compiled: {len(candidates)} actionable candidate(s)"); return report

if __name__=="__main__": compile_final_report(load_config())
