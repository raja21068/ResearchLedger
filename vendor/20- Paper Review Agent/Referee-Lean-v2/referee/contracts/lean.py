from __future__ import annotations
from typing import Any
from .schemas import obj, arr, STR, STR_NULL, BOOL, NUM, FREE_OBJ, FREE_ARR, EVIDENCE_ANCHOR, CLAIM

LEAN_CANDIDATE_CONCERN = obj({
    "concern_id": STR,
    "title": STR,
    "severity": {"enum": ["major", "minor", "observation"]},
    "claim_ids": arr(STR),
    "evidence_anchor_ids": arr(STR),
    "failure_mechanism": STR,
    "scientific_consequence": STR,
    "minimum_resolution": STR,
    "closure_criterion": STR,
    "reviewer_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "external_verification_required": BOOL,
    "uncertainties": arr(STR),
    "suggested_validation_checks": arr(STR),
}, [
    "concern_id", "title", "severity", "claim_ids", "evidence_anchor_ids",
    "failure_mechanism", "scientific_consequence", "minimum_resolution",
    "closure_criterion", "reviewer_confidence", "external_verification_required",
    "uncertainties", "suggested_validation_checks",
])

LEAN_SPECIALIST_REQUEST = obj({
    "task_id": STR,
    "specialist": STR,
    "claim_ids": arr(STR),
    "objective": STR,
    "priority": {"enum": ["high", "medium", "low"]},
    "evidence_needs": arr(STR),
}, ["task_id", "specialist", "claim_ids", "objective", "priority", "evidence_needs"])

LEAN_LITERATURE_QUERY = obj({
    "query": STR,
    "goal": STR,
    "claim_ids": arr(STR),
}, ["query", "goal", "claim_ids"])

LEAN_CORE_REVIEW_OUTPUT = obj({
    "review_version": {"const": "referee-lean-v2"},
    "classification": obj({
        "field": STR,
        "domain": STR,
        "design": STR,
        "inference_type": STR,
        "study_type": STR,
    }, ["field", "domain", "design", "inference_type", "study_type"], additional=True),
    "manuscript_summary": obj({
        "research_question": STR,
        "approach": STR,
        "main_results": STR,
        "claimed_contribution": STR,
        "developmental_stage": STR,
    }, ["research_question", "approach", "main_results", "claimed_contribution", "developmental_stage"]),
    "claims": arr(CLAIM),
    "evidence_anchors": arr(EVIDENCE_ANCHOR),
    "candidate_concerns": arr(LEAN_CANDIDATE_CONCERN),
    "minor_concerns": FREE_ARR,
    "strengths": FREE_ARR,
    "observations": FREE_ARR,
    "literature_queries": arr(LEAN_LITERATURE_QUERY),
    "specialist_requests": arr(LEAN_SPECIALIST_REQUEST),
    "overall_scientific_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "remaining_uncertainties": arr(STR),
}, [
    "review_version", "classification", "manuscript_summary", "claims", "evidence_anchors",
    "candidate_concerns", "minor_concerns", "strengths", "observations",
    "literature_queries", "specialist_requests", "overall_scientific_confidence",
    "remaining_uncertainties",
])

LEAN_SPECIALIST_RESULT = obj({
    "candidate_concerns": arr(LEAN_CANDIDATE_CONCERN),
    "evidence_anchors": arr(EVIDENCE_ANCHOR),
    "notes": FREE_ARR,
    "uncertainties": FREE_ARR,
}, ["candidate_concerns", "evidence_anchors", "notes", "uncertainties"])

LEAN_VERIFIER_ENTAILMENT = obj({
    "claim_mapping_valid": BOOL,
    "anchors_support_failure_mechanism": BOOL,
    "scientific_consequence_proportionate": BOOL,
    "minimum_resolution_sufficient": BOOL,
    "closure_criterion_testable": BOOL,
    "steelman_survival_supported": BOOL,
    "manuscript_contradiction_found": BOOL,
}, [
    "claim_mapping_valid", "anchors_support_failure_mechanism",
    "scientific_consequence_proportionate", "minimum_resolution_sufficient",
    "closure_criterion_testable", "steelman_survival_supported",
    "manuscript_contradiction_found",
])

LEAN_VERIFIER = obj({
    "status": {"enum": ["verified", "downgrade", "rejected", "needs_evidence"]},
    "severity": {"enum": ["major", "minor", "observation"]},
    "steelman": STR,
    "steelman_survives": BOOL,
    "steelman_survival_reason": STR,
    "rationale": STR,
    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "entailment": LEAN_VERIFIER_ENTAILMENT,
    "uncertainties": arr(STR),
}, [
    "status", "severity", "steelman", "steelman_survives", "steelman_survival_reason",
    "rationale", "confidence", "entailment", "uncertainties",
])
