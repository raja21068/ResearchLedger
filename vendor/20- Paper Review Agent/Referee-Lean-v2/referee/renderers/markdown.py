from __future__ import annotations
from ..models import ReviewState


def render_review_markdown(state: ReviewState) -> str:
    fr = state.final_review or {}
    brief = fr.get("decision_brief", {})
    lines = [
        "# Scientific Peer Review",
        "",
        f"**Run:** `{state.run_id}`  ",
        f"**Mode:** `{state.mode}`  ",
        f"**Status:** `{state.status}`",
        "",
        "## Decision brief",
    ]
    if isinstance(brief, dict):
        for k, v in brief.items():
            lines.append(f"- **{k.replace('_',' ').title()}:** {v}")
    else:
        lines.append(str(brief))
    lines += ["", "## Major concerns"]
    if not state.admitted_concerns:
        lines.append("No major/critical concern passed the evidence-lock admission gate.")
    for i, c in enumerate(state.admitted_concerns, 1):
        lines += [
            "",
            f"### {i}. {c.get('title','Untitled concern')}",
            f"**Severity:** {c.get('severity')}  ",
            f"**Affected claims:** {', '.join(c.get('claim_ids', []))}  ",
            f"**Evidence anchors:** {', '.join(c.get('evidence_anchor_ids', []))}",
            "",
            f"**Failure mechanism.** {c.get('failure_mechanism','')}",
            "",
            f"**Scientific consequence.** {c.get('scientific_consequence','')}",
            "",
            f"**Minimum resolution.** {c.get('minimum_resolution','')}",
            "",
            f"**Closure criterion.** {c.get('closure_criterion','')}",
        ]
    minor = fr.get("minor_comments") or []
    if minor:
        lines += ["", "## Minor comments"] + [f"- {x if isinstance(x,str) else x.get('text',x)}" for x in minor]
    if state.critical_gates:
        lines += ["", "## Critical gates"]
        for k, v in state.critical_gates.items():
            lines.append(f"- **{k}:** {v}")
    if state.reliability:
        lines += ["", "## Review reliability", f"{state.reliability}"]
    if state.journal_landscape:
        lines += ["", "## Journal landscape"]
        for j in state.journal_landscape:
            if isinstance(j, dict):
                lines.append(f"- **{j.get('journal', j.get('name',''))}** — {j.get('rationale','')}")
            else:
                lines.append(f"- {j}")
    if state.warnings:
        lines += ["", "## Validation warnings"] + [f"- {w}" for w in state.warnings]
    lines += ["", "## Run metrics", f"`{state.metrics}`", ""]
    return "\n".join(lines)
