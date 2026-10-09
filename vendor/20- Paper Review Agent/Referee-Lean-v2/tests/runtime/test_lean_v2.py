from __future__ import annotations
import asyncio
from pathlib import Path

from referee.config import ReviewConfig
from referee.engine import ReviewEngine
from referee.providers.scripted import ScriptedLLMProvider, ScriptedSearchProvider
from referee.stages import LEAN_INITIAL_STAGES


def _core():
    return {
        "review_version": "referee-lean-v2",
        "classification": {"field":"test","domain":"test","design":"observational","inference_type":"causal","study_type":"empirical"},
        "manuscript_summary": {"research_question":"Does X improve Y?","approach":"observational","main_results":"20% improvement claimed","claimed_contribution":"causal improvement claim","developmental_stage":"empirical manuscript"},
        "claims": [{
            "claim_id":"C001","text":"Treatment X improves outcome Y by 20%.","claim_type":"causal","centrality":"central","scope":"main result",
            "proof_burden":["causal identification"],"evidence_anchor_ids":["A001"],"support_status":"weak","confidence":"moderate","alternatives":[]
        }],
        "evidence_anchors": [{
            "anchor_id":"A001","source_type":"manuscript","document_id":"D1","locator":"body",
            "quote_or_fact":"We claim treatment X improves outcome Y by 20%.","supports":"C001","confidence":"high",
            "url":None,"content_status":None,"content_sha256":None
        }],
        "candidate_concerns": [{
            "concern_id":"MC001","title":"Causal identification is not established","severity":"major","claim_ids":["C001"],"evidence_anchor_ids":["A001"],
            "failure_mechanism":"The manuscript states a causal improvement claim but the supplied design description does not establish an intervention or identification strategy separating treatment from confounding.",
            "scientific_consequence":"The 20% result cannot be interpreted as a causal treatment effect on the evidence supplied.",
            "minimum_resolution":"Reframe the conclusion as associational unless a valid identification strategy is documented and justified.",
            "closure_criterion":"Remove causal language or provide and validate the identification strategy supporting a causal interpretation.",
            "reviewer_confidence":0.9,"external_verification_required":False,"uncertainties":[],"suggested_validation_checks":[]
        }],
        "minor_concerns":[],"strengths":[],"observations":[],"literature_queries":[],"specialist_requests":[],
        "overall_scientific_confidence":0.45,"remaining_uncertainties":[]
    }


def _verdict():
    return {
        "status":"verified","severity":"major","steelman":"The authors may intend the word improves descriptively rather than causally.",
        "steelman_survives":True,"steelman_survival_reason":"The registered central claim is explicitly causal, so the interpretation remains consequential.",
        "rationale":"The frozen claim and anchor support the concern and the requested correction is proportionate.","confidence":0.92,
        "entailment": {
            "claim_mapping_valid":True,"anchors_support_failure_mechanism":True,"scientific_consequence_proportionate":True,
            "minimum_resolution_sufficient":True,"closure_criterion_testable":True,"steelman_survival_supported":True,
            "manuscript_contradiction_found":False
        },
        "uncertainties":[]
    }


def test_lean_pipeline_has_seven_default_stages():
    assert len(LEAN_INITIAL_STAGES) == 7
    assert [s.stage_id for s in LEAN_INITIAL_STAGES] == [
        "L01_ingest","L02_core_review","L03_targeted_evidence","L04_targeted_specialists",
        "L05_hard_evidence_gate","L06_independent_verify","L07_finalize"
    ]


def test_lean_pipeline_smoke(tmp_path):
    paper=tmp_path/'paper.md'
    paper.write_text('# Paper\nWe claim treatment X improves outcome Y by 20%.',encoding='utf-8')
    responses={
        'lean_core_review':_core(),
        'lean_verify:MC-LEAN-CORE-REVIEWER-0001':_verdict(),
    }
    cfg=ReviewConfig(mode='deep',pipeline='lean',run_root=str(tmp_path/'runs'),enable_literature_search=False)
    engine=ReviewEngine(llm=ScriptedLLMProvider(responses),search=ScriptedSearchProvider(),config=cfg,package_root=str(Path(__file__).resolve().parents[2]))
    state=asyncio.run(engine.review([str(paper)],run_id='lean-smoke'))
    assert state.metrics['pipeline']=='lean'
    assert len(state.stage_records)==7
    assert len(state.admitted_concerns)==1
    assert state.admitted_concerns[0]['steelman'].startswith('The authors may')
    assert state.final_review_exportable is True
    assert not state.hard_invariant_failures
