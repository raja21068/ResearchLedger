"""`researchledger validate-paper <path>`: audits a manuscript's quantitative
assertions against the claim/evidence/run graph. `validate` checks the
graph is internally consistent; this checks the *manuscript* actually rests
on it — the other end of "paper statement -> claim -> evidence -> run ->
metrics -> raw artifact."

A "quantitative assertion" is any sentence, within a paragraph of
non-heading/non-table/non-comment lines, containing a digit outside of
inline code spans (so `` `E001.md` `` doesn't itself count as quantitative
just because it has a number in it). Paragraphs are
joined across hard-wrapped lines before sentence-splitting — otherwise a
sentence wrapped across two source lines gets counted twice and the
marker's position (right after the paragraph, not the last wrapped line
some prose formatter happened to break at) can be missed. It counts as
linked if the first non-blank line right after the paragraph carries a
`<!-- rl:claim=... [evidence=...] -->` marker (see validator.PROVENANCE_RE).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .models import load_claims, load_evidence
from .validator import PROVENANCE_RE, list_runs
from .workspace import Workspace

_QUANTITATIVE_RE = re.compile(r"\d")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


@dataclass
class PaperAuditResult:
    quantitative_assertions: int = 0
    linked_to_claims: int = 0
    backed_by_verified_evidence: int = 0
    backed_by_reproducible_runs: int = 0
    unsupported: int = 0
    stale_evidence_usage: int = 0
    unsupported_sentences: list[str] = field(default_factory=list)


def _is_prose_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith(("#", "<!--", "|"))


def _iter_paragraphs(lines: list[str]):
    """Yields (paragraph_text, first_line_after_index) for each block of
    consecutive prose lines, joined with spaces so a sentence hard-wrapped
    across source lines is scanned once, as one sentence."""
    buffer: list[str] = []
    for i, line in enumerate(lines):
        if _is_prose_line(line):
            buffer.append(line.strip())
            continue
        if buffer:
            yield " ".join(buffer), i
            buffer = []
    if buffer:
        yield " ".join(buffer), len(lines)


def audit_paper(ws: Workspace, paper_path: Path) -> PaperAuditResult:
    text = paper_path.read_text(encoding="utf-8")
    claims = load_claims(ws)
    evidence = load_evidence(ws)
    runs = list_runs(ws)
    lines = text.splitlines()
    result = PaperAuditResult()

    for raw_paragraph, next_line_index in _iter_paragraphs(lines):
        marker = PROVENANCE_RE.search(lines[next_line_index]) if next_line_index < len(lines) else None
        # Strip inline code spans before scanning for digits — a file/id
        # reference like `E001.md` or `research/decisions/D001.md` is not a
        # quantitative claim, it just happens to contain digits.
        paragraph = _INLINE_CODE_RE.sub("", raw_paragraph)
        for sentence in _SENTENCE_SPLIT_RE.split(paragraph):
            sentence = sentence.strip()
            if not sentence or not _QUANTITATIVE_RE.search(sentence):
                continue
            result.quantitative_assertions += 1

            if marker is None:
                result.unsupported += 1
                result.unsupported_sentences.append(sentence)
                continue

            result.linked_to_claims += 1
            claim_ids = [c.strip() for c in marker.group("claims").split(",") if c.strip()]
            verified = reproducible = stale = False
            explicitly_cited = [
                e.strip()
                for e in ((marker.group("evidence") or "").split(","))
                if e.strip()
            ]
            for cid in claim_ids:
                claim = claims.get(cid)
                if not claim:
                    continue

                # If the manuscript marker names concrete evidence, audit exactly
                # that evidence.  Otherwise treat the claim as recovered when it
                # has live verified support; merely retaining superseded evidence
                # in the claim's history must not keep the manuscript permanently
                # stale after replacement evidence has been verified.
                candidate_ids = explicitly_cited or claim.evidence
                candidate = [evidence[eid] for eid in candidate_ids if eid in evidence]
                live = [ev for ev in candidate if ev.status != "superseded"]

                if explicitly_cited:
                    stale = stale or any(ev.status == "superseded" for ev in candidate)
                else:
                    stale = stale or (bool(candidate) and not live and any(ev.status == "superseded" for ev in candidate))

                for ev in live:
                    if ev.status == "verified":
                        verified = True
                    for rid in ev.runs:
                        manifest = runs.get(rid)
                        if manifest and manifest.get("exit_code") == 0 and (manifest.get("git") or {}).get("commit"):
                            reproducible = True
            if verified:
                result.backed_by_verified_evidence += 1
            if reproducible:
                result.backed_by_reproducible_runs += 1
            if stale:
                result.stale_evidence_usage += 1

    return result


def render(result: PaperAuditResult) -> str:
    lines = [
        "Manuscript provenance audit",
        "",
        f"Quantitative assertions found:      {result.quantitative_assertions}",
        f"Linked to claim records:            {result.linked_to_claims}",
        f"Backed by verified evidence:        {result.backed_by_verified_evidence}",
        f"Backed by reproducible runs:        {result.backed_by_reproducible_runs}",
        f"Unsupported:                        {result.unsupported}",
        f"Stale/superseded evidence used:     {result.stale_evidence_usage}",
    ]
    if result.unsupported_sentences:
        lines.append("")
        lines.append("Unsupported assertions:")
        for sentence in result.unsupported_sentences:
            lines.append(f"  - {sentence}")
    return "\n".join(lines)
