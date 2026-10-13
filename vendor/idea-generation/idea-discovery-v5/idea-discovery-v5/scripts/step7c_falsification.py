"""V5 falsification zone.

Turns literature-surviving ideas into falsifiable contracts, attacks unnecessary
complexity, designs counterexamples, performs a blind independent verification,
and (when real MVE evidence exists) builds an evidence ledger for the final verdict.

Important epistemic rule:
- No empirical evidence => READY_FOR_MVE, never GREENLIGHT.
- GREENLIGHT requires an executed MVE evidence artifact plus an independent
  evidence assessment that supports the central claim strongly enough to justify
  a larger study.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from utils import ClaudeClient, load_json, save_json, save_markdown, log, print_banner
from step7_attack_loop import (
    AttackClient, run_phase10_scorecard, run_phase11_novelty_attack,
    run_phase12_matrix, run_phase13_reviewer, run_phase14_revision,
    evaluate_round,
)
from step6_novelty import run_literature_search
from citation_graph import deep_novelty_search

CONTRACT_SYSTEM = r"""You are a scientific hypothesis engineer. Convert the supplied research idea into a falsifiable hypothesis contract. Do not strengthen claims beyond the idea. Avoid vague success language. Every prediction must be observable and every falsifier must be concrete.
Return ONLY JSON:
{
 "idea_id":"IDEA-001",
 "central_hypothesis":"...",
 "null_hypothesis":"...",
 "mechanism_claim":"...",
 "observable_predictions":[{"prediction":"...","measure":"...","direction":"...","decision_threshold":"..."}],
 "supporting_evidence_would_be":["..."],
 "weakening_evidence_would_be":["..."],
 "falsifying_evidence_would_be":["..."],
 "competing_explanations":["..."],
 "confounders":["..."],
 "boundary_conditions":["..."],
 "minimal_decisive_experiment":"...",
 "contract_quality":"PASS|REVISE",
 "contract_issues":["..."]
}
"""

OCCAM_COUNTER_SYSTEM = r"""You are a hostile scientific falsifier. You are NOT trying to improve the idea. Try to make it fail cheaply and reveal whether its claimed mechanism is necessary.
Given only the hypothesis contract and method components, produce an Occam attack and counterexample plan.
Return ONLY JSON:
{
 "idea_id":"IDEA-001",
 "occam_tests":[{"remove_or_simplify":"...","what_same_result_would_imply":"...","priority":"HIGH|MEDIUM|LOW"}],
 "counterexample_tests":[{"test":"...","why_likely_to_break_claim":"...","expected_if_claim_true":"...","expected_if_claim_false":"..."}],
 "negative_controls":["..."],
 "positive_controls":["..."],
 "competing_explanation_tests":["..."],
 "leakage_or_shortcut_tests":["..."],
 "cheapest_high_information_test":"...",
 "complexity_justified":"YES|NO|UNCLEAR",
 "fatal_design_issue":"...",
 "verdict":"PASS|REVISE|KILL"
}
"""

BLIND_VERIFY_SYSTEM = r"""You are an independent scientific verifier operating blind to the idea generator's reasoning, enthusiasm, prior scores, and reviewer discussions. Judge only the hypothesis contract, proposed falsification tests, and the minimal experiment protocol. Prefer disconfirmation over confirmation. Do not infer missing evidence.
Return ONLY JSON:
{
 "idea_id":"IDEA-001",
 "testability":"PASS|REVISE|KILL",
 "mechanism_identifiability":"PASS|REVISE|KILL",
 "confounding_control":"PASS|REVISE|KILL",
 "counterexample_strength":"PASS|REVISE|KILL",
 "occam_status":"PASS|REVISE|KILL",
 "minimal_experiment_is_decisive":true,
 "unresolved_threats":["..."],
 "required_changes":["..."],
 "verdict":"PASS|REVISE|KILL",
 "reason":"..."
}
"""

MVE_SYSTEM = r"""You are designing a minimum viable experiment (MVE), not the full study. The MVE should be the cheapest credible experiment capable of falsifying or materially weakening the central hypothesis. It must include at least one strong baseline/control and one mechanism-discriminating test.
Return ONLY JSON:
{
 "idea_id":"IDEA-001",
 "objective":"...",
 "primary_claim_under_test":"...",
 "dataset_or_material":"...",
 "sampling_or_subset":"...",
 "strongest_baselines":["..."],
 "controls":["..."],
 "critical_ablation":"...",
 "primary_metric":"...",
 "secondary_metrics":["..."],
 "minimum_repeats_or_seeds":"...",
 "success_rule":"...",
 "falsification_rule":"...",
 "inconclusive_rule":"...",
 "leakage_checks":["..."],
 "artifacts_required":["raw results","config","seed list","environment/version info"],
 "estimated_cost":"...",
 "execution_command":"",
 "notes":"Do not auto-execute unless a human supplies/approves a concrete command."
}
"""

EVIDENCE_VERIFY_SYSTEM = r"""You are an independent evidence auditor. Assess ONLY the supplied hypothesis contract, MVE protocol, and executed MVE evidence. Do not see or use the generator's rationale or previous scores. Never convert absence of contradiction into support. Distinguish SUPPORTED from INCONCLUSIVE.
Return ONLY JSON:
{
 "idea_id":"IDEA-001",
 "evidence_quality":"HIGH|MEDIUM|LOW|INVALID",
 "protocol_adherence":"FULL|PARTIAL|FAILED",
 "primary_result":"...",
 "effect_and_uncertainty":"...",
 "supports_hypothesis":true,
 "supports_mechanism":true,
 "rules_out_key_alternatives":false,
 "negative_controls_passed":true,
 "leakage_checks_passed":true,
 "replication_strength":"...",
 "contradictions":["..."],
 "limitations":["..."],
 "verdict":"SUPPORTED|INCONCLUSIVE|CONTRADICTED|INVALID",
 "reason":"..."
}
"""

LEDGER_SYSTEM = r"""Build a conservative claim-evidence ledger from the contract and independent evidence assessment. Do not invent evidence. Each claim must explicitly show supporting, contradicting, and missing evidence.
Return ONLY JSON:
{
 "idea_id":"IDEA-001",
 "claims":[
   {"claim":"...","supporting_evidence":["..."],"contradicting_evidence":["..."],"missing_evidence":["..."],"status":"SUPPORTED|UNCERTAIN|CONTRADICTED"}
 ],
 "overall_status":"SUPPORTED|UNCERTAIN|CONTRADICTED",
 "remaining_alternatives":["..."],
 "full_study_justified":true,
 "reason":"..."
}
"""

REVISION_SYSTEM = r"""Revise the COMPLETE research idea to resolve the falsification-stage design blockers. This is a scientific revision, not prose polishing. If the core idea cannot be rescued without changing its identity or disguising a failed claim, kill it.
Return ONLY JSON:
{
 "decision":"REVISE|KILL",
 "reason":"...",
 "revised_idea":{},
 "changes":[{"blocker":"...","scientific_change":"..."}],
 "requires_new_literature_attack":true
}
"""


def validate_contract(x: dict) -> list[str]:
    issues=[]
    required=["central_hypothesis","null_hypothesis","mechanism_claim","observable_predictions","falsifying_evidence_would_be","minimal_decisive_experiment"]
    for k in required:
        if not x.get(k): issues.append(f"missing {k}")
    if x.get("contract_quality") not in {"PASS","REVISE"}: issues.append("contract_quality must be PASS|REVISE")
    if not isinstance(x.get("observable_predictions"),list) or not x.get("observable_predictions"): issues.append("at least one observable prediction required")
    return issues



def validate_occam(x: dict) -> list[str]:
    issues=[]
    if x.get("verdict") not in {"PASS","REVISE","KILL"}: issues.append("occam verdict must be PASS|REVISE|KILL")
    if not x.get("cheapest_high_information_test"): issues.append("missing cheapest_high_information_test")
    if not isinstance(x.get("negative_controls"),list) or not x.get("negative_controls"): issues.append("at least one negative control required")
    if not isinstance(x.get("counterexample_tests"),list): issues.append("counterexample_tests must be a list")
    return issues

def validate_mve_protocol(x: dict) -> list[str]:
    issues=[]
    for k in ["objective","primary_claim_under_test","critical_ablation","primary_metric","success_rule","falsification_rule","inconclusive_rule"]:
        if not x.get(k): issues.append(f"missing {k}")
    if not isinstance(x.get("strongest_baselines"),list) or not x.get("strongest_baselines"): issues.append("at least one strong baseline required")
    if not isinstance(x.get("controls"),list) or not x.get("controls"): issues.append("at least one control required")
    if not isinstance(x.get("leakage_checks"),list) or not x.get("leakage_checks"): issues.append("at least one leakage/shortcut check required")
    return issues

def validate_blind_verifier(x: dict) -> list[str]:
    issues=[]
    if x.get("verdict") not in {"PASS","REVISE","KILL"}: issues.append("blind verifier verdict must be PASS|REVISE|KILL")
    for k in ["testability","mechanism_identifiability","confounding_control","counterexample_strength","occam_status"]:
        if x.get(k) not in {"PASS","REVISE","KILL"}: issues.append(f"{k} must be PASS|REVISE|KILL")
    if not isinstance(x.get("minimal_experiment_is_decisive"),bool): issues.append("minimal_experiment_is_decisive must be boolean")
    return issues

def validate_mve_evidence(data: dict, idea_id: str) -> list[str]:
    issues=[]
    if not isinstance(data,dict): return ["evidence must be a JSON object"]
    if data.get("idea_id") != idea_id: issues.append("idea_id mismatch")
    if data.get("executed") is not True: issues.append("executed must be true")
    if not data.get("results"): issues.append("results are required")
    if not data.get("artifacts"): issues.append("artifacts are required")
    return issues


def final_decision_from_evidence(assessment: dict, ledger: dict) -> str:
    if assessment.get("verdict") == "CONTRADICTED" or ledger.get("overall_status") == "CONTRADICTED":
        return "KILL_OR_REVISE"
    if assessment.get("verdict") != "SUPPORTED":
        return "REVISE_EVIDENCE"
    if assessment.get("supports_hypothesis") is not True or assessment.get("supports_mechanism") is not True:
        return "REVISE_EVIDENCE"
    if assessment.get("evidence_quality") not in {"HIGH","MEDIUM"}:
        return "REVISE_EVIDENCE"
    if assessment.get("protocol_adherence") != "FULL":
        return "REVISE_EVIDENCE"
    if assessment.get("negative_controls_passed") is not True or assessment.get("leakage_checks_passed") is not True:
        return "REVISE_EVIDENCE"
    if ledger.get("overall_status") != "SUPPORTED" or ledger.get("full_study_justified") is not True:
        return "REVISE_EVIDENCE"
    return "GREENLIGHT"


def _search_for_current_idea(config: dict, idea: dict) -> dict:
    client=ClaudeClient(config=config)
    search=run_literature_search(idea, config=config, client=client)
    if config.get("citation_expansion",{}).get("enabled",True):
        try:
            expanded=deep_novelty_search(idea,search,config=config)
            search["citation_expanded_papers"]=expanded.get("expanded_papers",[])
        except Exception as exc:
            search["citation_expanded_papers"]=[]
            search["citation_expansion_meta"]={"error":str(exc)}
    return search


def rerun_literature_survival(config: dict, idea: dict, out_dir: Path) -> tuple[str, dict, list[dict]]:
    """Re-run Phase 10→14 after a falsification-driven scientific revision."""
    cfg=config.get("attack_loop",{})
    attacker=AttackClient(config)
    current=copy.deepcopy(idea)
    history=[]
    max_rounds=int(cfg.get("max_rounds",4))
    for r in range(1,max_rounds+1):
        rd=out_dir/f"reattack_{r:02d}"; rd.mkdir(parents=True,exist_ok=True)
        search=_search_for_current_idea(config,current); save_json(search,str(rd/"literature_search.json"))
        s=run_phase10_scorecard(attacker,current,search); save_json(s,str(rd/"phase10_scorecard.json"))
        n=run_phase11_novelty_attack(attacker,current,search); save_json(n,str(rd/"phase11_novelty_attack.json"))
        m=run_phase12_matrix(attacker,current,search,n); save_json(m,str(rd/"phase12_novelty_matrix.json"))
        rv=run_phase13_reviewer(attacker,current,search,s,n,m); save_json(rv,str(rd/"phase13_reviewer_attack.json"))
        ev=evaluate_round(s,n,m,rv,cfg); save_json(ev,str(rd/"round_evaluation.json"))
        bundle={"round":r,"scorecard":s,"novelty_attack":n,"novelty_matrix":m,"reviewer_attack":rv,"evaluation":ev}; history.append(bundle)
        if ev.get("decision")=="GREENLIGHT": return "GREENLIGHT",current,history
        rev=run_phase14_revision(attacker,current,bundle); save_json(rev,str(rd/"phase14_revision_or_kill.json"))
        if rev.get("decision")!="REVISE" or not isinstance(rev.get("revised_idea"),dict): return "KILL",current,history
        current=rev["revised_idea"]
    return "KILL_MAX_ROUNDS",current,history


def _blind_payload(contract: dict, occam: dict, mve: dict) -> dict:
    return {"hypothesis_contract":contract,"falsification_plan":occam,"mve_protocol":mve}


def _md(data: dict) -> str:
    s=data.get("summary",{})
    lines=["# V5 Falsification Zone","",f"Generated: {data.get('generated','')}","",
           "> Final GREENLIGHT requires real executed MVE evidence. Missing evidence yields READY_FOR_MVE, never a simulated pass.","",
           f"- GREENLIGHT: {s.get('greenlight',0)}",f"- READY_FOR_MVE: {s.get('ready_for_mve',0)}",f"- REVISE/INCONCLUSIVE: {s.get('revise',0)}",f"- KILL: {s.get('kill',0)}","" ]
    for x in data.get("ideas",[]):
        lines.append(f"## {x.get('idea_id')} — {x.get('final_decision')}")
        lines.append(f"- Falsification rounds: {x.get('rounds_run',0)}")
        if x.get("mve_evidence_present") is not None: lines.append(f"- MVE evidence present: {x.get('mve_evidence_present')}")
        if x.get("reason"): lines.append(f"- Reason: {x.get('reason')}")
        lines.append("")
    return "\n".join(lines)


def run_falsification(config: dict) -> dict:
    print_banner("STEP 7: V5 FALSIFICATION ZONE")
    out=Path(config["pipeline"]["output_dir"])
    fcfg=config.get("falsification",{})
    enabled=fcfg.get("enabled",True)
    attack=load_json(str(out/"attack_loop_summary.json"))
    provisional=[x for x in attack.get("ideas",[]) if x.get("final_decision")=="GREENLIGHT" and isinstance(x.get("final_idea"),dict)]
    if not enabled:
        data={"generated":datetime.now().isoformat(),"enabled":False,"ideas":[],"summary":{}}
        save_json(data,str(out/"falsification_summary.json")); return data

    author=ClaudeClient(config=config)
    verifier=AttackClient(config)
    root=out/"falsification"; root.mkdir(parents=True,exist_ok=True)
    raw_evidence=fcfg.get("evidence_dir")
    if raw_evidence:
        rp=Path(raw_evidence)
        evidence_dir = rp if rp.is_absolute() or (rp.parts and rp.parts[0] == out.name) else out/rp
    else:
        evidence_dir=out/"mve_evidence"
    evidence_dir.mkdir(parents=True,exist_ok=True)
    max_rounds=int(fcfg.get("max_rounds",2))
    portfolio=[]

    for item in provisional:
        current=copy.deepcopy(item["final_idea"]); iid=current.get("idea_id",item.get("idea_id"))
        current["idea_id"]=iid; idir=root/iid; idir.mkdir(parents=True,exist_ok=True)
        hist=[]; final="UNRESOLVED"; reason=""; evidence_present=False; evidence_assessment=None; ledger=None
        for rnd in range(1,max_rounds+1):
            occam = mve = blind = None
            rd=idir/f"round_{rnd:02d}"; rd.mkdir(parents=True,exist_ok=True)
            save_json(current,str(rd/"idea_entering_falsification.json"))

            contract=author.ask_json(CONTRACT_SYSTEM,json.dumps({"idea":current},ensure_ascii=False)[:24000],temperature=0.0)
            contract["idea_id"]=iid; issues=validate_contract(contract)
            if issues: contract["_validation_errors"]=issues
            save_json(contract,str(rd/"phase15_hypothesis_contract.json"))
            if issues or contract.get("contract_quality")!="PASS":
                design_verdict="REVISE"
            else:
                occam=verifier.ask_json(OCCAM_COUNTER_SYSTEM,json.dumps({"hypothesis_contract":contract,"method_sketch":current.get("method_sketch",{})},ensure_ascii=False)[:26000],temperature=0.0)
                occam["idea_id"]=iid
                occam_issues=validate_occam(occam)
                if occam_issues: occam["_validation_errors"]=occam_issues
                save_json(occam,str(rd/"phase16_occam_counterexample.json"))
                mve=author.ask_json(MVE_SYSTEM,json.dumps({"hypothesis_contract":contract,"falsification_plan":occam,"idea_constraints":{"feasibility":current.get("feasibility",{}),"experiment_design":current.get("experiment_design",{})}},ensure_ascii=False)[:28000],temperature=0.0)
                mve["idea_id"]=iid
                mve_issues=validate_mve_protocol(mve)
                if mve_issues: mve["_validation_errors"]=mve_issues
                save_json(mve,str(rd/"phase18_mve_protocol.json"))
                blind=verifier.ask_json(BLIND_VERIFY_SYSTEM,json.dumps(_blind_payload(contract,occam,mve),ensure_ascii=False)[:30000],temperature=0.0)
                blind["idea_id"]=iid
                blind_issues=validate_blind_verifier(blind)
                if blind_issues: blind["_validation_errors"]=blind_issues
                save_json(blind,str(rd/"phase17_blind_verifier.json"))
                if occam_issues or mve_issues or blind_issues:
                    design_verdict="REVISE"
                else:
                    design_verdict=blind.get("verdict","REVISE")

            round_record={"round":rnd,"contract":contract,"design_verdict":design_verdict}
            if isinstance(occam,dict): round_record["occam_counterexample"]=occam
            if isinstance(mve,dict): round_record["mve_protocol"]=mve
            if isinstance(blind,dict): round_record["blind_verifier"]=blind
            hist.append(round_record)

            if design_verdict=="KILL" or (isinstance(occam,dict) and occam.get("verdict")=="KILL"):
                final="KILL"; reason="Falsification design review found a fatal scientific flaw before MVE."; break
            if design_verdict!="PASS" or (isinstance(occam,dict) and occam.get("verdict")=="REVISE"):
                rev=author.ask_json(REVISION_SYSTEM,json.dumps({"idea":current,"hypothesis_contract":contract,"occam":occam or {},"blind_verifier":blind or {}},ensure_ascii=False)[:32000],temperature=0.0)
                save_json(rev,str(rd/"falsification_revision.json"))
                if rev.get("decision")!="REVISE" or not isinstance(rev.get("revised_idea"),dict):
                    final="KILL"; reason=rev.get("reason","Unrescuable falsification design flaw."); break
                revised=rev["revised_idea"]; revised["idea_id"]=iid; revised.setdefault("source_gap",current.get("source_gap"))
                status,reattacked,re_hist=rerun_literature_survival(config,revised,rd/"phase10_restart")
                round_record["literature_restart"]={"decision":status,"history":re_hist}
                if status!="GREENLIGHT":
                    final="KILL"; reason="Falsification-driven revision failed the restarted literature/reviewer attack loop."; break
                current=reattacked
                continue

            # Design survives. Real evidence is now mandatory for final GREENLIGHT.
            ep=evidence_dir/f"{iid}.json"
            if not ep.exists():
                final="READY_FOR_MVE"; reason=f"No executed MVE evidence found at {ep}."; evidence_present=False; break
            evidence_present=True
            try: evidence=load_json(str(ep))
            except Exception as exc:
                final="REVISE_EVIDENCE"; reason=f"Could not parse MVE evidence: {exc}"; break
            ev_issues=validate_mve_evidence(evidence,iid)
            if ev_issues:
                final="REVISE_EVIDENCE"; reason="; ".join(ev_issues); save_json({"validation_errors":ev_issues},str(rd/"mve_evidence_validation.json")); break
            evidence_assessment=verifier.ask_json(EVIDENCE_VERIFY_SYSTEM,json.dumps({"hypothesis_contract":contract,"mve_protocol":mve,"executed_mve_evidence":evidence},ensure_ascii=False)[:42000],temperature=0.0)
            evidence_assessment["idea_id"]=iid; save_json(evidence_assessment,str(rd/"phase19_evidence_assessment.json"))
            ledger=verifier.ask_json(LEDGER_SYSTEM,json.dumps({"hypothesis_contract":contract,"evidence_assessment":evidence_assessment,"executed_mve_evidence":evidence},ensure_ascii=False)[:42000],temperature=0.0)
            ledger["idea_id"]=iid; save_json(ledger,str(rd/"phase19_evidence_ledger.json"))
            decision=final_decision_from_evidence(evidence_assessment,ledger)
            if decision=="GREENLIGHT":
                final="GREENLIGHT"; reason="Literature, reviewer, falsification design, and executed MVE evidence all survived."; save_json(current,str(idir/"final_idea.json")); break
            if decision=="KILL_OR_REVISE":
                final="KILL"; reason="Executed MVE contradicted the central claim or evidence ledger."; break
            final="REVISE_EVIDENCE"; reason="Executed MVE is inconclusive or insufficiently controlled; do not greenlight the full study."; break
        else:
            final="KILL_MAX_ROUNDS"; reason="Falsification revision budget exhausted without a defensible design."

        portfolio.append({"idea_id":iid,"final_decision":final,"rounds_run":len(hist),"final_idea":current if final in {"GREENLIGHT","READY_FOR_MVE","REVISE_EVIDENCE"} else None,"mve_evidence_present":evidence_present,"evidence_assessment":evidence_assessment,"evidence_ledger":ledger,"reason":reason,"history":hist,"literature_attack_rounds":item.get("rounds_run",0)})

    summary={
        "greenlight":sum(x["final_decision"]=="GREENLIGHT" for x in portfolio),
        "ready_for_mve":sum(x["final_decision"]=="READY_FOR_MVE" for x in portfolio),
        "revise":sum(x["final_decision"] in {"REVISE_EVIDENCE","KILL_MAX_ROUNDS"} for x in portfolio),
        "kill":sum(x["final_decision"]=="KILL" for x in portfolio),
        "total":len(portfolio),
    }
    data={"generated":datetime.now().isoformat(),"enabled":True,"verifier_provider":verifier.actual_provider,"policy":{"no_empirical_evidence_no_greenlight":True,"blind_verifier_excludes_generator_rationale":True,"falsification_revision_restarts_phase10":True,"greenlight_requires_executed_mve":True},"summary":summary,"ideas":portfolio}
    save_json(data,str(out/"falsification_summary.json")); save_markdown(_md(data),str(out/"falsification_summary.md"))
    return data

if __name__=="__main__":
    from utils import load_config
    run_falsification(load_config())
