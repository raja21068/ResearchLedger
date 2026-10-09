from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from .base import Stage
from .core import (
    IntakeStage, PolicySecurityStage, _call, _core_review_user_payload,
    _compact_docs, _enrich_search_result, _opened_content,
    _materialize_literature_anchors, _manuscript_fingerprint,
)
from .platform import PackageAuditStage, ReportingAuditStage, ReproducibilityAuditStage, ProvenanceAuditStage
from ..context_manager import ContextManager
from ..contracts import Concern, validate_json_contract
from ..contracts.lean import LEAN_CORE_REVIEW_OUTPUT, LEAN_SPECIALIST_RESULT, LEAN_VERIFIER
from ..models import ReviewState
from ..utils.hashing import stable_json_hash
from ..validation import validate_major_comment
from ..validation.identifiers import (
    append_evidence_anchors, canonicalize_core_claims, claim_alias_map,
    anchor_alias_map, remap_concern_references, allocate_concern_id, assert_unique_ids,
)
from ..verification import verify_anchor_integrity, assess_closure_test, CitationVerifier, citation_metrics


LEAN_SKILL_FAMILIES: dict[str, list[str]] = {
    "theory": ["09_construct_theory", "10_rival_theory_falsifiability"],
    "methods": ["11_empirical_design", "12_sampling_measurement"],
    "statistics_causal": ["13_causal_inference", "14_statistics"],
    "literature": ["04_reference_forensics", "05_literature_search", "07_novelty", "08_research_gap", "39_literature_search_provenance"],
    "computational": ["15_benchmark_epistemology", "16_model_validation", "17_ml_ai", "18_computational_simulation", "50_computational_science_numerics", "51_ml_for_science"],
    "reproducibility": ["26_code_reproducibility", "27_robustness_generalization", "29_reporting_guidelines"],
    "numerical": ["25_figures_tables", "38_equations_units_numerical_consistency"],
    "integrity": ["28_ethics_integrity", "37_retraction_citation_integrity", "42_review_bias_fairness"],
    "systematic_review_meta": ["19_systematic_review_meta"],
    "qualitative": ["20_qualitative"],
    "rct_intervention": ["21_rct_intervention"],
    "observational_epidemiology": ["22_observational_epidemiology"],
    "diagnostic_prognostic": ["23_diagnostic_prognostic"],
    "measurement_instrument": ["24_measurement_instrument"],
    "electrochemistry_fuel_cells": ["44_electrochemistry_fuel_cells", "52_experimental_metrology_uncertainty"],
    "materials_characterization": ["45_materials_characterization", "48_analytical_chemistry_measurement", "54_spectroscopy_microscopy"],
    "environmental_process": ["46_environmental_water_processes", "49_energy_lca_tea", "53_chemical_kinetics_transport", "55_scaleup_process_engineering"],
    "microbiology_omics": ["47_microbiology_biofilms_omics"],
    "energy_lca_tea": ["49_energy_lca_tea", "55_scaleup_process_engineering"],
    "metrology_measurement": ["48_analytical_chemistry_measurement", "52_experimental_metrology_uncertainty"],
}


def _append_lean_candidate(
    state: ReviewState,
    raw: dict[str, Any],
    *,
    source_agent: str,
    trace: dict[str, Any] | None = None,
    task_id: str | None = None,
    anchor_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    c = remap_concern_references(
        dict(raw or {}),
        claim_map=claim_alias_map(state),
        anchor_map={**anchor_alias_map(state), **(anchor_map or {})},
    )
    local = str(c.get("concern_id") or "")
    c["source_local_id"] = local or None
    c["concern_id"] = allocate_concern_id(state, source_agent=source_agent, task_id=task_id)
    c["_source_agent"] = source_agent
    if task_id:
        c["_task_id"] = task_id
    if trace:
        c["_generator"] = dict(trace)
    state.proposed_concerns.append(c)
    assert_unique_ids(state.proposed_concerns, "concern_id", "concern")
    return c


def _mode_limits(ctx) -> tuple[int, int, int]:
    if ctx.config.mode == "standard":
        return 1, min(4, int(ctx.config.literature_query_budget or 4)), 5
    if ctx.config.mode == "exhaustive":
        return min(6, int(ctx.config.specialist_limit or 6)), min(12, int(ctx.config.literature_query_budget or 12)), 10
    return min(3, int(ctx.config.specialist_limit or 3)), min(8, int(ctx.config.literature_query_budget or 8)), 8


class LeanIngestStage(Stage):
    stage_id = "L01_ingest"

    async def run(self, ctx, state):
        await IntakeStage().run(ctx, state)
        await PackageAuditStage().run(ctx, state)
        await PolicySecurityStage().run(ctx, state)
        state.mode_artifacts["pipeline"] = "lean-v2"


class LeanCoreReviewStage(Stage):
    stage_id = "L02_core_review"

    async def run(self, ctx, state):
        system = ctx.prompts.core("LEAN_CORE_REVIEWER_PROMPT.md")
        specialist_names = ", ".join(sorted(LEAN_SKILL_FAMILIES))
        user = (
            _core_review_user_payload(state)
            + "\n\nRUNTIME SPECIALIST ALLOWLIST:\n" + specialist_names
            + "\n\nUse only specialist names in this allowlist. Keep the claim registry to the 5–12 scientifically important claims."
        )
        trace: dict[str, Any] = {}
        out = await _call(
            ctx,
            "lean_core_review",
            system,
            user,
            schema=LEAN_CORE_REVIEW_OUTPUT,
            model=ctx.config.strategic_model,
            agent_id="lean-core-reviewer",
            trace_out=trace,
        )
        state.core_review = out
        state.classification = dict(out.get("classification") or {})
        state.classification["pipeline"] = "lean-v2"
        state.core_review_validation = {
            "status": "passed",
            "schema": "referee-lean-v2",
            "core_prompt_sha256": hashlib.sha256(system.encode("utf-8")).hexdigest(),
            "model_verification_fields_trusted_as_proof": False,
        }

        state.claims = []
        state.evidence_anchors = []
        anchor_map = append_evidence_anchors(
            state,
            out.get("evidence_anchors") or [],
            source_stage="LEAN_CORE",
            reviewer_id="core",
        )
        claim_map = canonicalize_core_claims(state, out.get("claims") or [], anchor_map=anchor_map)
        for a in state.evidence_anchors:
            supports = [claim_map.get(x, x) for x in str(a.get("supports") or "").split(",") if x]
            a["supports"] = ",".join(supports)

        for c in out.get("candidate_concerns") or []:
            _append_lean_candidate(state, c, source_agent="lean-core-reviewer", trace=trace, anchor_map=anchor_map)

        specialist_limit, literature_limit, _ = _mode_limits(ctx)
        tasks = []
        for i, task in enumerate(out.get("specialist_requests") or [], 1):
            if not isinstance(task, dict) or task.get("specialist") not in LEAN_SKILL_FAMILIES:
                continue
            row = dict(task)
            row["task_id"] = str(row.get("task_id") or f"LT{i:03d}")
            row["claim_ids"] = [claim_map.get(str(x), str(x)) for x in row.get("claim_ids") or []]
            tasks.append(row)
            if len(tasks) >= specialist_limit:
                break
        state.review_plan = tasks

        queries = []
        for q in out.get("literature_queries") or []:
            if not isinstance(q, dict) or not str(q.get("query") or "").strip():
                continue
            row = dict(q)
            row["claim_ids"] = [claim_map.get(str(x), str(x)) for x in row.get("claim_ids") or []]
            queries.append(row)
            if len(queries) >= literature_limit:
                break
        state.mode_artifacts["lean_literature_queries"] = queries
        state.mode_artifacts["lean_core_trace"] = trace
        ctx.checkpoints.write_artifact("lean_core_review.json", state.core_review)


class LeanEvidenceStage(Stage):
    stage_id = "L03_targeted_evidence"

    async def run(self, ctx, state):
        await ReportingAuditStage().run(ctx, state)
        await ReproducibilityAuditStage().run(ctx, state)

        queries = list(state.mode_artifacts.get("lean_literature_queries") or [])
        if not ctx.config.enable_literature_search or not queries:
            state.literature_status = {"status": "not_requested" if not queries else "disabled", "queries": len(queries)}
            return

        if not ctx.search:
            state.search_ledger = [{**q, "results": [], "status": "search-provider-unavailable"} for q in queries]
            state.literature_status = {"status": "unavailable", "queries": len(queries), "results": 0, "opened_sources": 0}
            state.warnings.append("Lean v2 requested external evidence but no search provider was available; external-evidence concerns fail closed.")
            return

        sem = asyncio.Semaphore(ctx.config.max_concurrency)

        async def one(q):
            async with sem:
                ctx.budget.consume_search()
                raw = await ctx.search.search(q.get("query", ""), limit=8)
                enriched = await asyncio.gather(*(_enrich_search_result(ctx.search, r) for r in raw[:8]))
                return {**q, "results": enriched}

        state.search_ledger = await asyncio.gather(*(one(q) for q in queries))
        state.external_evidence = [
            r for row in state.search_ledger for r in (row.get("results") or [])
            if isinstance(r, dict) and _opened_content(r)
        ]
        opened = len(state.external_evidence)
        total = sum(len(row.get("results") or []) for row in state.search_ledger)
        state.literature_status = {
            "status": "available" if opened else "insufficient",
            "queries": len(queries), "results": total, "opened_sources": opened,
        }
        ctx.checkpoints.write_artifact("lean_search_ledger.json", state.search_ledger)


class LeanSpecialistStage(Stage):
    stage_id = "L04_targeted_specialists"

    async def run(self, ctx, state):
        specialist_limit, _, _ = _mode_limits(ctx)
        tasks = list(state.review_plan)[:specialist_limit]
        if not tasks:
            state.specialist_results = {}
            return
        sem = asyncio.Semaphore(ctx.config.max_concurrency)

        async def run_one(task: dict[str, Any]):
            family = str(task.get("specialist") or "")
            skills = LEAN_SKILL_FAMILIES.get(family, [])
            if not skills:
                return task, {}, {}
            system = ctx.prompts.core("LEAN_SPECIALIST_EXECUTOR_PROMPT.md") + "\n\n" + "\n\n".join(ctx.prompts.skill(s) for s in skills)
            claim_ids = set(task.get("claim_ids") or [])
            claims = [c for c in state.claims if not claim_ids or c.get("claim_id") in claim_ids]
            context = ContextManager(max_chars=20000).for_claims(state.document_map.get("documents", []), claims)
            user = (
                "SPECIALIST FAMILY:\n" + family
                + "\n\nTASK:\n" + json.dumps(task, ensure_ascii=False)
                + "\n\nCLAIMS:\n" + json.dumps(claims, ensure_ascii=False)[:10000]
                + "\n\nCLAIM-CENTERED MANUSCRIPT CONTEXT:\n" + context
                + "\n\nOPENED EXTERNAL EVIDENCE / SEARCH LEDGER:\n" + json.dumps(state.search_ledger, ensure_ascii=False)[:22000]
            )
            trace: dict[str, Any] = {}
            async with sem:
                out = await _call(
                    ctx,
                    f"lean_specialist:{family}",
                    system,
                    user,
                    schema=LEAN_SPECIALIST_RESULT,
                    agent_id=f"lean-specialist-executor:{family}:{task.get('task_id')}",
                    trace_out=trace,
                )
            return task, out, trace

        results = await asyncio.gather(*(run_one(t) for t in tasks))
        for task, out, trace in results:
            family = str(task.get("specialist") or "")
            task_id = str(task.get("task_id") or family)
            state.specialist_results[task_id] = {"specialist": family, "result": out}
            if not isinstance(out, dict):
                continue
            raw_anchors = list(out.get("evidence_anchors") or [])
            if any(str(a.get("source_type") or "").lower() in {"external", "literature"} for a in raw_anchors if isinstance(a, dict)):
                raw_anchors = _materialize_literature_anchors(raw_anchors, state.search_ledger)
            anchor_map = append_evidence_anchors(
                state, raw_anchors, source_stage="LEAN_SPECIALIST", reviewer_id=family, trajectory_id=task_id
            )
            for c in out.get("candidate_concerns") or []:
                _append_lean_candidate(state, c, source_agent="lean-specialist-executor", trace=trace, task_id=task_id, anchor_map=anchor_map)

        ctx.checkpoints.write_artifact("lean_specialist_results.json", state.specialist_results)


async def _citation_verify_external(ctx, state: ReviewState) -> None:
    verifier = CitationVerifier()
    existing = {str(r.get("citation_id")) for r in state.citation_verification_records if isinstance(r, dict)}
    for a in state.evidence_anchors:
        aid = str(a.get("anchor_id") or "")
        if not aid or aid in existing or str(a.get("source_type") or "").lower() not in {"external", "literature"}:
            continue
        source_record = a.get("_matched_source_record")
        asserted = {
            "citation_id": aid,
            "source_identifier": a.get("document_id") or a.get("source_identifier"),
            "title": a.get("_matched_title") or a.get("title"),
            "year": a.get("year"),
        }
        proposition = str(a.get("quote_or_fact") or "")
        record = verifier.verify(asserted, source_record, proposition=proposition)
        if record.get("proposition_support") == "uncertain" and source_record:
            content = str(source_record.get("raw_content") or source_record.get("content") or source_record.get("text") or "")
            if content:
                schema = {
                    "type": "object", "additionalProperties": False,
                    "required": ["status", "supporting_passage", "contradicting_passage", "confidence"],
                    "properties": {
                        "status": {"enum": ["supported", "contradicted", "uncertain", "not_assessable"]},
                        "supporting_passage": {"type": "string"},
                        "contradicting_passage": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                }
                entail = await _call(
                    ctx,
                    f"lean_external_entailment:{aid}",
                    "You are the Referee Lean independent evidence verifier. Determine only whether the frozen source content supports the asserted proposition. Do not add claims or citations. Return strict JSON.",
                    "ASSERTED PROPOSITION:\n" + proposition + "\n\nFROZEN SOURCE CONTENT:\n" + content[:16000],
                    schema=schema,
                    model=ctx.config.verifier_model or ctx.config.model,
                    agent_id=f"lean-independent-verifier:citation:{aid}",
                )
                record = verifier.verify(asserted, source_record, proposition=proposition, entailment=entail)
        state.citation_verification_records.append(record)
        existing.add(aid)
    state.metrics["citation_metrics"] = citation_metrics(state.citation_verification_records)


class LeanHardGateStage(Stage):
    stage_id = "L05_hard_evidence_gate"

    async def run(self, ctx, state):
        await _citation_verify_external(ctx, state)
        known_claims = {str(c.get("claim_id")) for c in state.claims if isinstance(c, dict) and c.get("claim_id")}
        known_anchors = {str(a.get("anchor_id")) for a in state.evidence_anchors if isinstance(a, dict) and a.get("anchor_id")}
        integrity_report = verify_anchor_integrity(state.evidence_anchors, state.document_map.get("documents", []))
        integrity = {str(r.get("anchor_id")): r for r in integrity_report.get("anchors", [])}
        citation = {str(r.get("citation_id")): r for r in state.citation_verification_records if isinstance(r, dict)}
        passed, rejected, minor = [], [], []

        for raw in state.proposed_concerns:
            c = dict(raw)
            if c.get("severity") != "major":
                minor.append(c)
                continue
            errors: list[str] = []
            for key in ("title", "failure_mechanism", "scientific_consequence", "minimum_resolution", "closure_criterion"):
                if not str(c.get(key) or "").strip():
                    errors.append(f"{key} empty")
            claims = [str(x) for x in c.get("claim_ids") or []]
            anchors = [str(x) for x in c.get("evidence_anchor_ids") or []]
            if not claims:
                errors.append("claim_ids empty")
            if not anchors:
                errors.append("evidence_anchor_ids empty")
            unknown_claims = sorted(set(claims) - known_claims)
            unknown_anchors = sorted(set(anchors) - known_anchors)
            if unknown_claims:
                errors.append(f"unknown claims: {unknown_claims}")
            if unknown_anchors:
                errors.append(f"unknown anchors: {unknown_anchors}")
            try:
                conf = float(c.get("reviewer_confidence"))
                if conf < 0.50:
                    errors.append("reviewer_confidence below 0.50")
            except Exception:
                errors.append("reviewer_confidence invalid")
            closure = assess_closure_test(str(c.get("closure_criterion") or ""))
            if not closure.get("actionable"):
                errors.append("closure criterion failed deterministic actionability check")
            for aid in anchors:
                rec = integrity.get(aid) or {}
                if rec.get("status") not in {"verified", "external_verified"}:
                    errors.append(f"anchor failed deterministic integrity check: {aid}")
                anchor = next((a for a in state.evidence_anchors if a.get("anchor_id") == aid), {})
                if str(anchor.get("source_type") or "").lower() in {"external", "literature"}:
                    vr = citation.get(aid) or {}
                    if not (
                        vr.get("existence_status") == "verified"
                        and vr.get("metadata_status") in {"match", "partial_match"}
                        and vr.get("source_content_available") is True
                        and vr.get("proposition_support") == "supported"
                        and not vr.get("contradicting_passages")
                    ):
                        errors.append(f"external anchor lacks decisive citation verification: {aid}")
            if c.get("external_verification_required") is True:
                errors.append("candidate still requires external verification")
            c["hard_gate"] = {
                "status": "passed" if not errors else "failed",
                "errors": errors,
                "closure": closure,
            }
            if errors:
                c["status"] = "rejected_at_hard_gate"
                c["admission_errors"] = errors
                rejected.append(c)
            else:
                c["status"] = "passed_hard_gate"
                passed.append(c)

        state.provenance_candidates = passed
        state.rejected_concerns.extend(rejected)
        state.mode_artifacts["lean_minor_candidates"] = minor
        state.mode_artifacts["lean_anchor_integrity"] = integrity_report
        ctx.checkpoints.write_artifact("lean_hard_gate.json", {
            "passed": passed, "rejected": rejected, "minor_candidates": minor, "anchor_integrity": integrity_report,
        })


class LeanIndependentVerifierStage(Stage):
    stage_id = "L06_independent_verify"

    async def run(self, ctx, state):
        if not state.provenance_candidates:
            state.verification_candidates = []
            return
        claim_by_id = {c.get("claim_id"): c for c in state.claims if isinstance(c, dict)}
        anchor_by_id = {a.get("anchor_id"): a for a in state.evidence_anchors if isinstance(a, dict)}
        manuscript_sha = _manuscript_fingerprint(state)
        system = ctx.prompts.core("LEAN_INDEPENDENT_VERIFIER_PROMPT.md")
        sem = asyncio.Semaphore(ctx.config.max_concurrency)

        async def verify_one(c: dict[str, Any]):
            claims = [claim_by_id[x] for x in c.get("claim_ids") or [] if x in claim_by_id]
            anchors = [anchor_by_id[x] for x in c.get("evidence_anchor_ids") or [] if x in anchor_by_id]
            context = ContextManager(max_chars=16000).for_claims(state.document_map.get("documents", []), claims)
            candidate_hash = stable_json_hash({k: v for k, v in c.items() if not str(k).startswith("_") and k not in {"hard_gate", "status"}})
            frozen = {
                "manuscript_sha256": manuscript_sha,
                "claim_registry_sha256": stable_json_hash(claims),
                "anchor_bundle_sha256": stable_json_hash(anchors),
                "candidate_sha256": candidate_hash,
            }
            user = (
                "FROZEN CANDIDATE:\n" + json.dumps(c, ensure_ascii=False)
                + "\n\nFROZEN CLAIMS:\n" + json.dumps(claims, ensure_ascii=False)
                + "\n\nFROZEN ANCHORS:\n" + json.dumps(anchors, ensure_ascii=False)
                + "\n\nRELEVANT MANUSCRIPT CONTEXT:\n" + context
            )
            trace: dict[str, Any] = {}
            async with sem:
                verdict = await _call(
                    ctx,
                    f"lean_verify:{c.get('concern_id')}",
                    system,
                    user,
                    schema=LEAN_VERIFIER,
                    model=ctx.config.verifier_model or ctx.config.model,
                    agent_id=f"lean-independent-verifier:{c.get('concern_id')}",
                    trace_out=trace,
                )
            generator = c.get("_generator") or {}
            post_errors: list[str] = []
            if generator.get("context_id") and generator.get("context_id") == trace.get("context_id"):
                post_errors.append("verifier context is not independent from generator context")
            if generator.get("agent_id") and generator.get("agent_id") == trace.get("agent_id"):
                post_errors.append("verifier identity is not independent from generator identity")

            ent = verdict.get("entailment") or {}
            required = (
                "claim_mapping_valid", "anchors_support_failure_mechanism",
                "scientific_consequence_proportionate", "minimum_resolution_sufficient",
                "closure_criterion_testable", "steelman_survival_supported",
            )
            verified_major = verdict.get("status") == "verified" and verdict.get("severity") == "major"
            if verified_major:
                for key in required:
                    if ent.get(key) is not True:
                        post_errors.append(f"independent verifier did not affirm {key}")
                if ent.get("manuscript_contradiction_found") is not False:
                    post_errors.append("independent verifier found or could not exclude manuscript contradiction")
                if verdict.get("steelman_survives") is not True:
                    post_errors.append("candidate did not survive independent steelman")

            final_concern = None
            status = "rejected"
            if verified_major and not post_errors:
                final_concern = {
                    "concern_id": c.get("concern_id"),
                    "title": c.get("title"),
                    "severity": "major",
                    "claim_ids": list(c.get("claim_ids") or []),
                    "evidence_anchor_ids": list(c.get("evidence_anchor_ids") or []),
                    "failure_mechanism": c.get("failure_mechanism"),
                    "scientific_consequence": c.get("scientific_consequence"),
                    "minimum_resolution": c.get("minimum_resolution"),
                    "closure_criterion": c.get("closure_criterion"),
                    "reviewer_confidence": min(float(c.get("reviewer_confidence") or 0.0), float(verdict.get("confidence") or 0.0)),
                    "steelman": verdict.get("steelman"),
                    "steelman_survives": True,
                    "steelman_survival_reason": verdict.get("steelman_survival_reason"),
                    "external_verification_required": False,
                    "uncertainties": list(dict.fromkeys(list(c.get("uncertainties") or []) + list(verdict.get("uncertainties") or []))),
                    "suggested_validation_checks": list(c.get("suggested_validation_checks") or []),
                    "status": "admitted",
                    "hard_gate": c.get("hard_gate"),
                    "_generator": generator,
                }
                errors = validate_major_comment(final_concern, set(anchor_by_id), set(claim_by_id))
                if errors:
                    post_errors.extend(errors)
                    final_concern = None
                else:
                    status = "verified"

            if final_concern is not None:
                canonical = Concern.from_dict(final_concern)
                concern_sha = stable_json_hash(canonical.scientific_payload())
            else:
                concern_sha = None
            record = {
                "concern_id": c.get("concern_id"),
                "generator_run_id": generator.get("request_id"),
                "generator_agent_id": generator.get("agent_id"),
                "generator_context_id": generator.get("context_id"),
                "generator_model": generator.get("model"),
                "verifier_run_id": trace.get("request_id"),
                "verifier_agent_id": trace.get("agent_id"),
                "verifier_context_id": trace.get("context_id"),
                "verifier_model": trace.get("model"),
                "verifier_prompt_sha256": hashlib.sha256(system.encode("utf-8")).hexdigest(),
                "manuscript_sha256": frozen["manuscript_sha256"],
                "claim_registry_sha256": frozen["claim_registry_sha256"],
                "anchor_bundle_sha256": frozen["anchor_bundle_sha256"],
                "candidate_sha256": frozen["candidate_sha256"],
                "concern_sha256": concern_sha,
                "verification_status": status,
                "judge_status": verdict.get("status"),
                "verdict": verdict,
                "verifier_output_sha256": stable_json_hash(verdict),
                "deterministic_postcheck": {"status": "passed" if not post_errors else "failed", "errors": post_errors},
            }
            return c, final_concern, record

        results = await asyncio.gather(*(verify_one(c) for c in state.provenance_candidates))
        admitted: list[dict[str, Any]] = []
        for candidate, final_concern, record in results:
            state.verification_records.append(record)
            verdict = record.get("verdict") or {}
            if final_concern is not None and record.get("verification_status") == "verified":
                final_concern["independent_verification"] = {
                    "verification_status": "verified",
                    "verifier_run_id": record.get("verifier_run_id"),
                    "verifier_agent_id": record.get("verifier_agent_id"),
                    "verifier_context_id": record.get("verifier_context_id"),
                    "verifier_model": record.get("verifier_model"),
                    "verifier_output_sha256": record.get("verifier_output_sha256"),
                }
                admitted.append(final_concern)
            else:
                rejected = dict(candidate)
                rejected["status"] = f"rejected_after_verification:{verdict.get('status', 'rejected')}"
                rejected["admission_errors"] = list((record.get("deterministic_postcheck") or {}).get("errors") or [])
                if verdict.get("status") == "downgrade" or verdict.get("severity") in {"minor", "observation"}:
                    state.mode_artifacts.setdefault("lean_downgraded", []).append({
                        "text": candidate.get("title") + ": " + candidate.get("failure_mechanism", ""),
                        "verification_rationale": verdict.get("rationale"),
                    })
                state.rejected_concerns.append(rejected)

        _, _, max_major = _mode_limits(ctx)
        claim_centrality = {c.get("claim_id"): str(c.get("centrality") or c.get("importance") or "supporting") for c in state.claims}
        weight = {"central": 3.0, "supporting": 2.0, "peripheral": 1.0}
        def score(c):
            cent = max((weight.get(claim_centrality.get(x, "supporting"), 2.0) for x in c.get("claim_ids") or []), default=1.0)
            return cent * float(c.get("reviewer_confidence") or 0.0)
        admitted.sort(key=score, reverse=True)
        state.priority_ranking = [{"concern_id": c.get("concern_id"), "score": score(c), "method": "deterministic-centrality-x-confidence"} for c in admitted]
        state.admitted_concerns = admitted[:max_major]
        state.verification_candidates = list(state.admitted_concerns)
        ctx.checkpoints.write_artifact("lean_independent_verification.json", state.verification_records)


class LeanFinalizeStage(Stage):
    stage_id = "L07_finalize"

    async def run(self, ctx, state):
        await ProvenanceAuditStage().run(ctx, state)
        core = state.core_review or {}
        minor = []
        for item in core.get("minor_concerns") or []:
            if isinstance(item, str):
                minor.append(item)
            elif isinstance(item, dict):
                minor.append(item.get("text") or item.get("issue") or item.get("title") or str(item))
        for c in state.mode_artifacts.get("lean_minor_candidates") or []:
            minor.append(str(c.get("title") or "Minor concern") + ": " + str(c.get("failure_mechanism") or ""))
        for item in state.mode_artifacts.get("lean_downgraded") or []:
            minor.append(item)
        minor = minor[: ctx.config.max_minor_comments]
        strengths = core.get("strengths") or []
        summary = core.get("manuscript_summary") or {}
        confidence = core.get("overall_scientific_confidence")
        has_major = bool(state.admitted_concerns)
        state.critical_gates = {
            "evidence_lock": {"status": "pass", "admitted_major_concerns": len(state.admitted_concerns)},
            "independent_verification": {"status": "pass", "verified_records": sum(r.get("verification_status") == "verified" for r in state.verification_records)},
            "external_evidence": {"status": "pass" if not any("external anchor" in str(x.get("admission_errors")) for x in state.rejected_concerns) else "warn", "opened_sources": len(state.external_evidence)},
        }
        state.final_review = {
            "decision_brief": {
                "pipeline": "Referee Lean v2",
                "research_question": summary.get("research_question", ""),
                "claimed_contribution": summary.get("claimed_contribution", ""),
                "developmental_stage": summary.get("developmental_stage", ""),
                "verified_major_concerns": len(state.admitted_concerns),
                "no_material_scientific_barriers": not has_major,
                "overall_scientific_confidence": confidence,
                "recommendation_basis": (
                    "Major scientific issues remain and require closure before the central conclusions should be treated as secure."
                    if has_major else
                    "No major concern passed the evidence-locked independent-verification gate; remaining comments are minor, uncertain, or out of scope."
                ),
            },
            "minor_comments": minor,
            "strengths": strengths,
            "limitations": list(core.get("remaining_uncertainties") or []),
        }
        state.reliability = {"status": "not_run_in_lean_default", "note": "Use the legacy/audit path for repeated trajectories and repeatability analysis."}
        state.metrics["pipeline"] = "lean-v2"
        state.metrics["lean_default_stage_count"] = 7
        state.metrics["lean_reasoning_roles"] = 3
        ctx.checkpoints.write_artifact("lean_final_review.json", state.final_review)


LEAN_INITIAL_STAGES = [
    LeanIngestStage(),
    LeanCoreReviewStage(),
    LeanEvidenceStage(),
    LeanSpecialistStage(),
    LeanHardGateStage(),
    LeanIndependentVerifierStage(),
    LeanFinalizeStage(),
]
