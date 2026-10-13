"""
step7_attack_loop.py — Iterative adversarial idea survival loop (V5.0 (literature/reviewer sub-loop))

Implements the user's Phase 10–14 process as a real bounded state machine:
  Phase 10 Scorecard
  Phase 11 Novelty Attack
  Phase 12 Novelty Matrix
  Phase 13 Reviewer #1 Attack
  Phase 14 Revise-or-Kill
Then repeats Phases 10–13 on the revised idea until GREENLIGHT or KILL.

Each round is persisted independently for auditability.
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from utils import ClaudeClient, load_config, load_json, save_json, save_markdown, log, print_banner
from step6_novelty import run_literature_search
from citation_graph import deep_novelty_search

ROOT = Path(__file__).resolve().parent.parent
PROMPT_DIR = ROOT / "prompts"


def _read_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


PHASE10_SOURCE = _read_prompt("phase10_scorecard.txt")
PHASE11_SOURCE = _read_prompt("phase11_novelty_attack.txt")
PHASE12_SOURCE = _read_prompt("phase12_novelty_matrix.txt")
PHASE13_SOURCE = _read_prompt("phase13_reviewer_attack.txt")
PHASE14_SOURCE = _read_prompt("phase14_revision_or_kill.txt")


SCORECARD_JSON_CONTRACT = r"""
Return ONLY JSON in this exact structure:
{
  "idea_id": "IDEA-001",
  "criteria": [
    {"criterion":"Problem importance","weight":15,"score":0,"rationale":"..."},
    {"criterion":"Evidence that the gap exists","weight":15,"score":0,"rationale":"..."},
    {"criterion":"Novelty vs. recent literature","weight":20,"score":0,"rationale":"..."},
    {"criterion":"Scientific insight","weight":15,"score":0,"rationale":"..."},
    {"criterion":"Experimental feasibility","weight":10,"score":0,"rationale":"..."},
    {"criterion":"Potential impact","weight":10,"score":0,"rationale":"..."},
    {"criterion":"Evaluation strength possible","weight":10,"score":0,"rationale":"..."},
    {"criterion":"Reproducibility","weight":5,"score":0,"rationale":"..."}
  ],
  "total_score": 0,
  "strongest_aspects": ["..."],
  "major_weaknesses": ["..."],
  "novelty_check": {"genuinely_new":"...","likely_incremental_or_known":"...","uncertainty":"..."},
  "evidence_needed": ["..."],
  "how_to_improve": ["..."],
  "final_assessment": "...",
  "blocking_issues": ["..."]
}
Scores must obey each maximum weight. total_score must equal the sum of the eight criterion scores.
"""

NOVELTY_ATTACK_JSON_CONTRACT = r"""
Return ONLY JSON:
{
  "idea_id":"IDEA-001",
  "attack_goal":"Find papers that make this idea NOT novel.",
  "search_coverage":{
    "exact_mechanism":true,
    "conceptual_synonyms":true,
    "alternate_terminology":true,
    "adjacent_domains":true,
    "latest_conference_or_recent_work":true,
    "arxiv":true,
    "patents_when_relevant":"NOT_RELEVANT|CHECKED|NOT_CONFIGURED"
  },
  "papers_that_threaten_novelty":[
    {
      "title":"...",
      "year":2026,
      "source":"semantic_scholar|arxiv|openalex|citation_graph|other",
      "collision_type":"same_mechanism|same_problem_different_term|same_hypothesis|adjacent_domain_precedent|partial_overlap",
      "severity":"FATAL|MAJOR|MINOR",
      "why_it_threatens_novelty":"...",
      "remaining_delta":"..."
    }
  ],
  "direct_collision":false,
  "strongest_collision":"...",
  "patent_relevance":"HIGH|MEDIUM|LOW",
  "unresolved_search_gaps":["..."],
  "verdict":"SURVIVES|REVISE|KILL",
  "reason":"..."
}
A KILL verdict is appropriate when the core intellectual contribution is already demonstrated by prior work and cannot be rescued by a non-cosmetic pivot.
"""

MATRIX_JSON_CONTRACT = r"""
Return ONLY JSON:
{
  "idea_id":"IDEA-001",
  "competitors":[
    {"paper_id":"P1","title":"...","year":2026,"why_strong_competitor":"..."}
  ],
  "features":["feature 1","feature 2","feature 3","External validation","Mechanism analysis","Uncertainty"],
  "matrix":[
    {"feature":"feature 1","my_work":"✓","P1":"✓","P2":"△","P3":"✗"}
  ],
  "already_covered":["..."],
  "genuinely_novel":["..."],
  "closest_competing_paper":"...",
  "novelty_type":"conceptual|methodological|empirical|new_combination|none",
  "intellectual_contribution":"...",
  "checkmark_warning":"Explain why the verdict is not based on counting checkmarks.",
  "verdict":"DISTINCT|WEAK_DELTA|NOT_NOVEL",
  "reason":"..."
}
Use only ✓, △, or ✗ in matrix cells. Compare against 3–5 strongest competitors when at least 3 credible competitors are available.
"""

REVIEWER_JSON_CONTRACT = r"""
Return ONLY JSON:
{
  "idea_id":"IDEA-001",
  "criticisms":[
    {"rank":1,"criticism":"...","severity":"Fatal|Major|Minor","why":"...","fix_before_coding":"..."}
  ],
  "fatal_flaws_to_fix_before_coding":["..."],
  "major_flaws_to_fix_before_coding":["..."],
  "strongest_rejection_case":"...",
  "verdict":"SURVIVES|REVISE|KILL",
  "reason":"..."
}
Provide exactly 10 ranked criticisms. A Fatal criticism means the project should change or be abandoned before coding unless a genuine scientific pivot fixes it.
"""

REVISION_JSON_CONTRACT = r"""
Return ONLY JSON:
{
  "idea_id":"IDEA-001",
  "decision":"REVISE|KILL",
  "reason":"...",
  "revised_idea": { },
  "change_log":[
    {"source_phase":"10|11|12|13","issue":"...","change":"...","why_this_is_non_cosmetic":"..."}
  ],
  "unresolved_issues":["..."],
  "is_scientific_pivot":false,
  "pivot_description":""
}
If decision=REVISE, revised_idea must be the COMPLETE idea object, preserve idea_id/source_gap traceability, and include a testable hypothesis/null hypothesis. If decision=KILL, revised_idea may be null.
"""


class AttackClient:
    """Use an independent attacker model when configured; fall back to Claude."""

    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get("attack_loop", {}).get("attacker_provider", "auto").lower()
        self.openai_model = config.get("attack_loop", {}).get("openai_model", "gpt-4o")
        self._claude = ClaudeClient(config=config)
        self._openai = None
        self.actual_provider = "claude"

        if self.provider in {"auto", "openai"} and os.environ.get("OPENAI_API_KEY"):
            try:
                import openai
                self._openai = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
                self.actual_provider = "openai"
            except Exception as exc:
                log.warning(f"Independent OpenAI attacker unavailable; using Claude: {exc}")

    def ask_json(self, system: str, user: str, temperature: float = 0.0) -> dict:
        if self.actual_provider != "openai":
            return self._claude.ask_json(system, user, temperature=temperature)

        attempts = int(self.config.get("api", {}).get("json_repair_attempts", 2)) + 1
        prompt_user = user
        last_error = None
        for _ in range(attempts):
            try:
                resp = self._openai.chat.completions.create(
                    model=self.openai_model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt_user},
                    ],
                )
                raw = resp.choices[0].message.content or ""
                return ClaudeClient._parse_json_payload(raw)
            except Exception as exc:
                last_error = exc
                prompt_user = (
                    "Return ONLY valid JSON matching the requested contract. "
                    f"Previous response/error: {str(exc)[:500]}\n\nOriginal task:\n{user}"
                )
        raise ValueError(f"OpenAI attacker failed to return JSON: {last_error}")


def _compact_search(search: dict, max_each: int = 10) -> dict:
    return {
        "core_claims": search.get("core_claims", []),
        "query_plan": search.get("query_plan", []),
        "queries_used": search.get("queries_used", []),
        "semantic_scholar_results": search.get("semantic_scholar_results", [])[:max_each],
        "arxiv_results": search.get("arxiv_results", [])[:max_each],
        "openalex_results": search.get("openalex_results", [])[:max_each],
        "recent_concurrent_results": search.get("recent_concurrent_results", [])[:max_each],
        "citation_expanded_papers": search.get("citation_expanded_papers", [])[:max_each],
        "total_unique_papers_found": search.get("total_unique_papers_found", 0),
    }


def _criterion(scorecard: dict, name: str) -> dict:
    wanted = name.strip().lower()
    for row in scorecard.get("criteria", []):
        if str(row.get("criterion", "")).strip().lower() == wanted:
            return row
    return {}


def validate_scorecard(scorecard: dict) -> list[str]:
    expected = {
        "Problem importance": 15,
        "Evidence that the gap exists": 15,
        "Novelty vs. recent literature": 20,
        "Scientific insight": 15,
        "Experimental feasibility": 10,
        "Potential impact": 10,
        "Evaluation strength possible": 10,
        "Reproducibility": 5,
    }
    issues = []
    seen = {}
    for row in scorecard.get("criteria", []):
        name = row.get("criterion")
        if name in expected:
            seen[name] = row
    for name, weight in expected.items():
        if name not in seen:
            issues.append(f"Missing scorecard criterion: {name}")
            continue
        row = seen[name]
        try:
            score = float(row.get("score", -1))
        except Exception:
            score = -1
        if row.get("weight") != weight:
            issues.append(f"{name}: weight must be {weight}")
        if score < 0 or score > weight:
            issues.append(f"{name}: score {score} outside 0..{weight}")
    calc = sum(float(seen[n].get("score", 0)) for n in expected if n in seen)
    try:
        stated = float(scorecard.get("total_score", -1))
    except Exception:
        stated = -1
    if abs(calc - stated) > 1e-6:
        issues.append(f"total_score mismatch: stated={stated}, calculated={calc}")
    return issues



def validate_novelty_attack(data: dict) -> list[str]:
    issues = []
    if data.get("verdict") not in {"SURVIVES", "REVISE", "KILL"}:
        issues.append("novelty attack verdict must be SURVIVES|REVISE|KILL")
    if data.get("patent_relevance") not in {"HIGH", "MEDIUM", "LOW"}:
        issues.append("patent_relevance must be HIGH|MEDIUM|LOW")
    if not isinstance(data.get("direct_collision"), bool):
        issues.append("direct_collision must be boolean")
    if data.get("direct_collision") is True and data.get("verdict") == "SURVIVES":
        issues.append("direct_collision=true is inconsistent with SURVIVES")
    coverage = data.get("search_coverage", {})
    if coverage.get("patents_when_relevant") not in {"NOT_RELEVANT", "CHECKED", "NOT_CONFIGURED"}:
        issues.append("patents_when_relevant must be NOT_RELEVANT|CHECKED|NOT_CONFIGURED")
    return issues


def validate_matrix(data: dict) -> list[str]:
    issues = []
    if data.get("verdict") not in {"DISTINCT", "WEAK_DELTA", "NOT_NOVEL"}:
        issues.append("matrix verdict must be DISTINCT|WEAK_DELTA|NOT_NOVEL")
    if data.get("novelty_type") not in {"conceptual", "methodological", "empirical", "new_combination", "none"}:
        issues.append("novelty_type is invalid")
    for row_i, row in enumerate(data.get("matrix", []), 1):
        if not isinstance(row, dict):
            issues.append(f"matrix row {row_i} is not an object")
            continue
        for key, value in row.items():
            if key == "feature":
                continue
            if value not in {"✓", "△", "✗"}:
                issues.append(f"matrix row {row_i} cell {key} must be ✓|△|✗")
    if data.get("verdict") == "DISTINCT" and not str(data.get("intellectual_contribution", "")).strip():
        issues.append("DISTINCT requires a non-empty intellectual_contribution")
    return issues


def validate_reviewer(data: dict) -> list[str]:
    issues = []
    crits = data.get("criticisms", [])
    if len(crits) != 10:
        issues.append(f"reviewer must return exactly 10 criticisms, got {len(crits)}")
    ranks = []
    fatal = 0
    for i, c in enumerate(crits, 1):
        if not isinstance(c, dict):
            issues.append(f"criticism {i} is not an object")
            continue
        ranks.append(c.get("rank"))
        sev = c.get("severity")
        if sev not in {"Fatal", "Major", "Minor"}:
            issues.append(f"criticism {i} severity must be Fatal|Major|Minor")
        if sev == "Fatal":
            fatal += 1
    if len(crits) == 10 and set(ranks) != set(range(1, 11)):
        issues.append("reviewer criticism ranks must be exactly 1..10")
    if data.get("verdict") not in {"SURVIVES", "REVISE", "KILL"}:
        issues.append("reviewer verdict must be SURVIVES|REVISE|KILL")
    if fatal and data.get("verdict") == "SURVIVES":
        issues.append("Reviewer cannot SURVIVE while Fatal criticisms remain")
    return issues


def validate_revision(data: dict, original: dict) -> list[str]:
    issues = []
    if data.get("decision") not in {"REVISE", "KILL"}:
        issues.append("revision decision must be REVISE|KILL")
        return issues
    if data.get("decision") == "REVISE":
        revised = data.get("revised_idea")
        if not isinstance(revised, dict) or not revised:
            issues.append("REVISE requires a complete revised_idea object")
            return issues
        if not revised.get("idea_id") and not original.get("idea_id"):
            issues.append("revised idea must retain idea_id")
        if not revised.get("source_gap") and not original.get("source_gap"):
            issues.append("revised idea must retain source_gap traceability")
        hyp = revised.get("hypothesis")
        if not isinstance(hyp, dict) or not str(hyp.get("statement", "")).strip():
            issues.append("revised idea requires a hypothesis statement")
        if not isinstance(hyp, dict) or not str(hyp.get("null_hypothesis", "")).strip():
            issues.append("revised idea requires a null hypothesis")
    return issues


def _repair_phase(client: AttackClient, system: str, user: str, first: dict, issues: list[str]) -> dict:
    repair_user = (
        "The previous response violates the deterministic output contract. "
        "Correct the payload without weakening the scientific criticism or inflating the idea. "
        "Return ONLY the corrected JSON.\n\n"
        f"VALIDATION ERRORS:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
        f"ORIGINAL TASK:\n{user[:26000]}\n\n"
        f"PREVIOUS RESPONSE:\n{json.dumps(first, ensure_ascii=False)[:16000]}"
    )
    return client.ask_json(system, repair_user, temperature=0.0)


def _repair_scorecard(client: AttackClient, idea: dict, search: dict, first: dict, issues: list[str]) -> dict:
    prompt = PHASE10_SOURCE + "\n\n" + SCORECARD_JSON_CONTRACT
    user = (
        "The previous scorecard violated deterministic scoring rules. Correct it without inflating scores.\n"
        f"VALIDATION ERRORS:\n{json.dumps(issues)}\n\n"
        f"IDEA:\n{json.dumps(idea, ensure_ascii=False)[:12000]}\n\n"
        f"LITERATURE EVIDENCE:\n{json.dumps(_compact_search(search), ensure_ascii=False)[:16000]}\n\n"
        f"PREVIOUS SCORECARD:\n{json.dumps(first, ensure_ascii=False)[:12000]}"
    )
    return client.ask_json(prompt, user, temperature=0.0)


def run_phase10_scorecard(client: AttackClient, idea: dict, search: dict) -> dict:
    system = PHASE10_SOURCE + "\n\n" + SCORECARD_JSON_CONTRACT
    user = (
        "Evaluate this proposed research idea. The study has not been conducted. "
        "Ground novelty/gap claims in the supplied literature evidence; state uncertainty where evidence is incomplete.\n\n"
        f"IDEA:\n{json.dumps(idea, indent=2, ensure_ascii=False)[:14000]}\n\n"
        f"LITERATURE EVIDENCE:\n{json.dumps(_compact_search(search), indent=1, ensure_ascii=False)[:18000]}"
    )
    result = client.ask_json(system, user, temperature=0.0)
    issues = validate_scorecard(result)
    if issues:
        result = _repair_scorecard(client, idea, search, result, issues)
        issues = validate_scorecard(result)
    if issues:
        result["_validation_errors"] = issues
    return result


def run_phase11_novelty_attack(client: AttackClient, idea: dict, search: dict) -> dict:
    system = (
        PHASE11_SOURCE
        + "\n\nYou are an adversarial novelty attacker. Your objective is falsification: actively look for evidence that the proposed contribution is already known."
        + "\n\n" + NOVELTY_ATTACK_JSON_CONTRACT
    )
    patent_status = "NOT_CONFIGURED"
    user = (
        f"IDEA:\n{json.dumps(idea, indent=2, ensure_ascii=False)[:14000]}\n\n"
        f"SEARCH RESULTS:\n{json.dumps(_compact_search(search), indent=1, ensure_ascii=False)[:22000]}\n\n"
        f"PATENT SEARCH CAPABILITY IN THIS RUN: {patent_status}. "
        "If patents are materially relevant, flag patent_relevance=HIGH and list that as an unresolved search gap; do not pretend patents were checked."
    )
    result = client.ask_json(system, user, temperature=0.0)
    issues = validate_novelty_attack(result)
    if issues:
        result = _repair_phase(client, system, user, result, issues)
        issues = validate_novelty_attack(result)
    if issues:
        result["_validation_errors"] = issues
    return result


def run_phase12_matrix(client: AttackClient, idea: dict, search: dict, novelty_attack: dict) -> dict:
    system = PHASE12_SOURCE + "\n\n" + MATRIX_JSON_CONTRACT
    user = (
        f"IDEA:\n{json.dumps(idea, indent=2, ensure_ascii=False)[:12000]}\n\n"
        f"ADVERSARIAL NOVELTY ATTACK:\n{json.dumps(novelty_attack, indent=2, ensure_ascii=False)[:10000]}\n\n"
        f"SEARCH RESULTS:\n{json.dumps(_compact_search(search), indent=1, ensure_ascii=False)[:20000]}\n\n"
        "Use real titles from the supplied evidence. If fewer than 3 credible competitors exist, use what exists and explicitly state the evidence limitation."
    )
    result = client.ask_json(system, user, temperature=0.0)
    issues = validate_matrix(result)
    if issues:
        result = _repair_phase(client, system, user, result, issues)
        issues = validate_matrix(result)
    if issues:
        result["_validation_errors"] = issues
    return result


def run_phase13_reviewer(client: AttackClient, idea: dict, search: dict, scorecard: dict, novelty_attack: dict, matrix: dict) -> dict:
    system = PHASE13_SOURCE + "\n\n" + REVIEWER_JSON_CONTRACT
    user = (
        f"CURRENT IDEA:\n{json.dumps(idea, indent=2, ensure_ascii=False)[:12000]}\n\n"
        f"PHASE 10 SCORECARD:\n{json.dumps(scorecard, indent=2, ensure_ascii=False)[:10000]}\n\n"
        f"PHASE 11 NOVELTY ATTACK:\n{json.dumps(novelty_attack, indent=2, ensure_ascii=False)[:10000]}\n\n"
        f"PHASE 12 NOVELTY MATRIX:\n{json.dumps(matrix, indent=2, ensure_ascii=False)[:10000]}\n\n"
        f"LITERATURE EVIDENCE:\n{json.dumps(_compact_search(search), indent=1, ensure_ascii=False)[:16000]}"
    )
    result = client.ask_json(system, user, temperature=0.0)
    issues = validate_reviewer(result)
    if issues:
        result = _repair_phase(client, system, user, result, issues)
        issues = validate_reviewer(result)
    if issues:
        result["_validation_errors"] = issues
    return result


def evaluate_round(scorecard: dict, novelty_attack: dict, matrix: dict, reviewer: dict, cfg: dict) -> dict:
    threshold = float(cfg.get("greenlight_score", 80))
    min_novelty = float(cfg.get("min_novelty_component", 14))
    fatal = [
        x for x in reviewer.get("criticisms", [])
        if str(x.get("severity", "")).strip().lower() == "fatal"
    ]
    score = float(scorecard.get("total_score", 0) or 0)
    novelty_component = float(_criterion(scorecard, "Novelty vs. recent literature").get("score", 0) or 0)

    blockers = []
    if score < threshold:
        blockers.append(f"scorecard {score:.1f} < greenlight threshold {threshold:.1f}")
    if novelty_component < min_novelty:
        blockers.append(f"novelty component {novelty_component:.1f} < {min_novelty:.1f}")
    if novelty_attack.get("verdict") != "SURVIVES":
        blockers.append(f"novelty attack verdict={novelty_attack.get('verdict')}")
    if matrix.get("verdict") != "DISTINCT":
        blockers.append(f"novelty matrix verdict={matrix.get('verdict')}")
    if not str(matrix.get("intellectual_contribution", "")).strip():
        blockers.append("novelty matrix lacks an explicit intellectual contribution")
    if reviewer.get("verdict") != "SURVIVES":
        blockers.append(f"Reviewer #1 verdict={reviewer.get('verdict')}")
    if fatal:
        blockers.append(f"{len(fatal)} Fatal reviewer criticism(s)")
    if novelty_attack.get("patent_relevance") == "HIGH" and \
       novelty_attack.get("search_coverage", {}).get("patents_when_relevant") == "NOT_CONFIGURED":
        blockers.append("high patent relevance but patent search is not configured")

    # Core novelty collision can kill immediately.
    hard_kill = (
        novelty_attack.get("verdict") == "KILL"
        or matrix.get("verdict") == "NOT_NOVEL"
        or reviewer.get("verdict") == "KILL"
    )

    if not blockers:
        decision = "GREENLIGHT"
    elif hard_kill:
        decision = "KILL_OR_PIVOT"
    else:
        decision = "REVISE"

    return {
        "decision": decision,
        "score": score,
        "novelty_component_score": novelty_component,
        "fatal_count": len(fatal),
        "blockers": blockers,
    }


def run_phase14_revision(client: AttackClient, idea: dict, round_bundle: dict) -> dict:
    system = PHASE14_SOURCE + "\n\n" + REVISION_JSON_CONTRACT
    user = (
        f"CURRENT IDEA:\n{json.dumps(idea, indent=2, ensure_ascii=False)[:14000]}\n\n"
        f"FULL ATTACK RECORD:\n{json.dumps(round_bundle, indent=2, ensure_ascii=False)[:30000]}\n\n"
        "Do not merely rewrite prose. If the idea survives, make concrete scientific changes that resolve the blockers. "
        "If it cannot be rescued without disguising prior work, return KILL."
    )
    result = client.ask_json(system, user, temperature=0.0)
    if result.get("decision") == "REVISE":
        revised = result.get("revised_idea") or {}
        revised["idea_id"] = idea.get("idea_id")
        if idea.get("source_gap") and not revised.get("source_gap"):
            revised["source_gap"] = idea.get("source_gap")
        result["revised_idea"] = revised
    issues = validate_revision(result, idea)
    if issues:
        result = _repair_phase(client, system, user, result, issues)
        if result.get("decision") == "REVISE":
            revised = result.get("revised_idea") or {}
            revised["idea_id"] = idea.get("idea_id")
            if idea.get("source_gap") and not revised.get("source_gap"):
                revised["source_gap"] = idea.get("source_gap")
            result["revised_idea"] = revised
        issues = validate_revision(result, idea)
    if issues:
        result["_validation_errors"] = issues
    return result


def _md_for_summary(data: dict) -> str:
    lines = [
        "# Iterative Adversarial Attack Loop",
        "",
        f"Generated: {data.get('generated','')}",
        f"Attacker model: **{data.get('attacker_provider','')}**",
        "",
        "## Portfolio",
        "",
        f"- GREENLIGHT: {data.get('summary',{}).get('greenlight',0)}",
        f"- KILL: {data.get('summary',{}).get('kill',0)}",
        f"- MAX-ROUNDS/UNRESOLVED: {data.get('summary',{}).get('unresolved',0)}",
        "",
    ]
    for item in data.get("ideas", []):
        lines.append(f"## {item.get('idea_id')} — {item.get('final_decision')}")
        lines.append(f"- Rounds: {item.get('rounds_run')}")
        lines.append(f"- Final score: {item.get('final_score')}")
        if item.get("final_blockers"):
            lines.append("- Remaining blockers:")
            lines.extend(f"  - {x}" for x in item["final_blockers"])
        lines.append("")
        for rnd in item.get("history", []):
            ev = rnd.get("evaluation", {})
            lines.append(
                f"  - Round {rnd.get('round')}: score={ev.get('score')} "
                f"decision={ev.get('decision')} blockers={len(ev.get('blockers',[]))}"
            )
        lines.append("")
    return "\n".join(lines)


def run_attack_loop(config: dict) -> dict:
    """Run iterative Phase 10–14 attack/revision loop for every generated idea."""
    print_banner("STEP 6: ITERATIVE ATTACK → CHECK → REVISE LOOP")

    output_dir = Path(config["pipeline"]["output_dir"])
    loop_cfg = config.get("attack_loop", {})
    max_rounds = int(loop_cfg.get("max_rounds", 4))
    enabled = bool(loop_cfg.get("enabled", True))

    ideas_report = load_json(str(output_dir / "idea_report.json"))
    ideas = ideas_report.get("ideas", [])
    if not enabled:
        result = {"generated": datetime.now().isoformat(), "enabled": False, "ideas": [], "summary": {}}
        save_json(result, str(output_dir / "attack_loop_summary.json"))
        return result

    attacker = AttackClient(config)
    root = output_dir / "attack_loop"
    root.mkdir(parents=True, exist_ok=True)
    portfolio = []

    for idx, original in enumerate(ideas, 1):
        current = copy.deepcopy(original)
        idea_id = current.get("idea_id") or f"IDEA-{idx:03d}"
        current["idea_id"] = idea_id
        idea_dir = root / idea_id
        idea_dir.mkdir(parents=True, exist_ok=True)
        history = []
        final_decision = "UNRESOLVED"
        final_eval = {}

        log.info(f"\n[{idea_id}] Starting iterative adversarial loop (max {max_rounds} rounds)")

        for round_no in range(1, max_rounds + 1):
            round_dir = idea_dir / f"round_{round_no:02d}"
            round_dir.mkdir(parents=True, exist_ok=True)
            save_json(current, str(round_dir / "idea_entering_round.json"))

            # Search is repeated after each revision: attacks must evaluate the current idea, not the stale original.
            search_client = ClaudeClient(config=config)
            search = run_literature_search(current, config=config, client=search_client)
            if config.get("citation_expansion", {}).get("enabled", True):
                try:
                    expanded = deep_novelty_search(current, search, config=config)
                    search["citation_expanded_papers"] = expanded.get("expanded_papers", [])
                    search["citation_expansion_meta"] = {
                        "citation_hops": expanded.get("citation_hops", 0),
                        "total_expanded": expanded.get("total_expanded", 0),
                        "total_recent_filtered": expanded.get("total_recent_filtered", 0),
                    }
                except Exception as exc:
                    log.warning(f"[{idea_id}] citation expansion degraded gracefully: {exc}")
                    search["citation_expanded_papers"] = []
                    search["citation_expansion_meta"] = {"error": str(exc)}
            save_json(search, str(round_dir / "literature_search.json"))

            scorecard = run_phase10_scorecard(attacker, current, search)
            save_json(scorecard, str(round_dir / "phase10_scorecard.json"))

            novelty_attack = run_phase11_novelty_attack(attacker, current, search)
            save_json(novelty_attack, str(round_dir / "phase11_novelty_attack.json"))

            matrix = run_phase12_matrix(attacker, current, search, novelty_attack)
            save_json(matrix, str(round_dir / "phase12_novelty_matrix.json"))

            reviewer = run_phase13_reviewer(attacker, current, search, scorecard, novelty_attack, matrix)
            save_json(reviewer, str(round_dir / "phase13_reviewer_attack.json"))

            evaluation = evaluate_round(scorecard, novelty_attack, matrix, reviewer, loop_cfg)
            save_json(evaluation, str(round_dir / "round_evaluation.json"))

            bundle = {
                "round": round_no,
                "scorecard": scorecard,
                "novelty_attack": novelty_attack,
                "novelty_matrix": matrix,
                "reviewer_attack": reviewer,
                "evaluation": evaluation,
            }
            history.append(bundle)
            final_eval = evaluation

            if evaluation["decision"] == "GREENLIGHT":
                final_decision = "GREENLIGHT"
                save_json(current, str(idea_dir / "final_idea.json"))
                break

            revision = run_phase14_revision(attacker, current, bundle)
            save_json(revision, str(round_dir / "phase14_revision_or_kill.json"))

            if revision.get("decision") == "KILL":
                final_decision = "KILL"
                break

            revised = revision.get("revised_idea")
            if not isinstance(revised, dict) or not revised:
                final_decision = "KILL"
                final_eval.setdefault("blockers", []).append("revision stage returned no complete revised idea")
                break

            # A revision must retain traceability and hypothesis structure.
            if not revised.get("source_gap"):
                revised["source_gap"] = current.get("source_gap")
            if not isinstance(revised.get("hypothesis"), dict) or not revised["hypothesis"].get("statement"):
                final_decision = "KILL"
                final_eval.setdefault("blockers", []).append("revised idea lost its testable hypothesis")
                break

            current = revised

        else:
            # Loop exhausted. Fail closed: an idea that never survived all attacks is not greenlit.
            final_decision = "KILL_MAX_ROUNDS"

        final_score = history[-1]["evaluation"].get("score") if history else None
        portfolio.append({
            "idea_id": idea_id,
            "original_title": original.get("title", ""),
            "final_title": current.get("title", ""),
            "final_decision": final_decision,
            "rounds_run": len(history),
            "final_score": final_score,
            "final_blockers": final_eval.get("blockers", []),
            "final_idea": current if final_decision == "GREENLIGHT" else None,
            "history": history,
        })

    summary = {
        "greenlight": sum(1 for x in portfolio if x["final_decision"] == "GREENLIGHT"),
        "kill": sum(1 for x in portfolio if x["final_decision"] == "KILL"),
        "unresolved": sum(1 for x in portfolio if x["final_decision"] == "KILL_MAX_ROUNDS"),
        "total": len(portfolio),
    }
    result = {
        "generated": datetime.now().isoformat(),
        "enabled": True,
        "max_rounds": max_rounds,
        "attacker_provider": attacker.actual_provider,
        "policy": {
            "greenlight_requires_all_four_phases_to_survive_same_round": True,
            "revised_ideas_restart_at_phase10": True,
            "fail_closed_after_max_rounds": True,
        },
        "summary": summary,
        "ideas": portfolio,
    }
    save_json(result, str(output_dir / "attack_loop_summary.json"))
    save_markdown(_md_for_summary(result), str(output_dir / "attack_loop_summary.md"))

    # Compatibility views for existing dashboard/report code. These are derived
    # from the FINAL loop round; no extra single-pass gate is executed.
    legacy_gates = []
    legacy_verifications = []
    for item in portfolio:
        last = item.get("history", [])[-1] if item.get("history") else {}
        attack = last.get("novelty_attack", {})
        matrix = last.get("novelty_matrix", {})
        review = last.get("reviewer_attack", {})
        scorecard = last.get("scorecard", {})
        final_dec = "GREENLIGHT" if item.get("final_decision") == "GREENLIGHT" else "KILL"
        legacy_gates.append({
            "idea_id": item.get("idea_id"),
            "decision": final_dec,
            "confidence": "HIGH" if final_dec == "GREENLIGHT" else "CONSERVATIVE",
            "strongest_counterargument": review.get("strongest_rejection_case", ""),
            "fatal_issues": review.get("fatal_flaws_to_fix_before_coding", []),
            "major_issues": review.get("major_flaws_to_fix_before_coding", []),
            "required_changes": item.get("final_blockers", []),
            "residual_risks": attack.get("unresolved_search_gaps", []),
            "rounds_run": item.get("rounds_run", 0),
            "_derived_from_iterative_loop": True,
        })
        novelty20 = float(_criterion(scorecard, "Novelty vs. recent literature").get("score", 0) or 0)
        mapped = "PROCEED" if final_dec == "GREENLIGHT" else (
            "ABANDON" if attack.get("verdict") == "KILL" or matrix.get("verdict") == "NOT_NOVEL"
            else "PIVOT"
        )
        overall_view = {
            "verdict": mapped,
            "novelty_score": round(novelty20 / 2.0, 1),
            "key_differentiator": matrix.get("intellectual_contribution", ""),
            "reviewer_risk": review.get("strongest_rejection_case", ""),
            "positioning_advice": matrix.get("reason", ""),
        }
        legacy_verifications.append({
            "idea_id": item.get("idea_id"),
            "title": item.get("final_title") or item.get("original_title"),
            "consensus": overall_view,
            "overall_assessment": overall_view,
            "assessment": {
                "overall_assessment": overall_view,
                "closest_papers": attack.get("papers_that_threaten_novelty", [])[:5],
            },
            "closest_papers": attack.get("papers_that_threaten_novelty", [])[:5],
            "_derived_from_iterative_loop": True,
        })

    legacy_gate = {
        "generated": result["generated"],
        "gates": legacy_gates,
        "portfolio_assessment": {
            "greenlight_count": sum(1 for g in legacy_gates if g["decision"] == "GREENLIGHT"),
            "revise_count": 0,
            "kill_count": sum(1 for g in legacy_gates if g["decision"] == "KILL"),
            "_derived_from_iterative_loop": True,
        },
    }
    legacy_novelty = {
        "generated": result["generated"],
        "verifications": legacy_verifications,
        "summary": {
            "total_verified": len(legacy_verifications),
            "proceed": sum(1 for v in legacy_verifications if v["overall_assessment"]["verdict"] == "PROCEED"),
            "proceed_with_caution": 0,
            "pivot": sum(1 for v in legacy_verifications if v["overall_assessment"]["verdict"] == "PIVOT"),
            "abandon": sum(1 for v in legacy_verifications if v["overall_assessment"]["verdict"] == "ABANDON"),
            "_derived_from_iterative_loop": True,
        },
    }
    save_json(legacy_gate, str(output_dir / "adversarial_gate.json"))
    save_json(legacy_novelty, str(output_dir / "novelty_report.json"))

    final_ideas = []
    for item in portfolio:
        idea_obj = item.get("final_idea")
        if not isinstance(idea_obj, dict):
            # Preserve the last entering/revised state for audit, even if killed.
            idea_obj = {
                "idea_id": item.get("idea_id"),
                "title": item.get("final_title") or item.get("original_title"),
            }
        idea_obj = copy.deepcopy(idea_obj)
        idea_obj["_attack_loop"] = {
            "final_decision": item.get("final_decision"),
            "rounds_run": item.get("rounds_run"),
            "final_score": item.get("final_score"),
            "final_blockers": item.get("final_blockers", []),
        }
        final_ideas.append(idea_obj)
    save_json(
        {"generated": result["generated"], "ideas": final_ideas, "_derived_from_iterative_loop": True},
        str(output_dir / "final_idea_report.json"),
    )
    return result


if __name__ == "__main__":
    run_attack_loop(load_config())
