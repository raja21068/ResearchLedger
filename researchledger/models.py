"""Typed views over research/{evidence,claims,decisions}/*.md.

v2 status vocabulary (see reference/run-ledger.md#status-vocabulary):
  Evidence: proposed -> observed -> checked -> verified, or contradicted /
            invalidated / superseded.
  Claim:    hypothesis -> provisional -> supported, or mixed / contradicted /
            withdrawn. A claim is never "verified" — only evidence is;
            `recompute_claim_status` is the one place that turns evidence
            states into a claim state, so "supported" always means
            "verified evidence with no live contradiction," never "one
            experiment happened to agree."

Field parsing accepts both the legacy v1 comma/pipe-delimited-string form and
the v2 canonical YAML-array form (`split_ids` handles both) so the graph
checks still run on not-yet-migrated files; `raw_frontmatter` is kept
alongside for schema validation, which is what actually flags the v1 form as
needing `researchledger migrate`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import parse_document, render_document, split_ids

EVIDENCE_STATUSES = {
    "proposed",
    "observed",
    "checked",
    "verified",
    "contradicted",
    "invalidated",
    "superseded",
}
CLAIM_STATUSES = {
    "hypothesis",
    "provisional",
    "supported",
    "mixed",
    "contradicted",
    "withdrawn",
}

# Back-compat aliases some validator/report code historically referenced.
VALID_EVIDENCE_STATUS = EVIDENCE_STATUSES
VALID_CLAIM_STATUS = CLAIM_STATUSES

# v1 -> v2 status rename, used by `researchledger migrate` as the starting
# point (claim status is then re-derived with recompute_claim_status, since
# a blind rename can't tell "supported" from "mixed").
V1_TO_V2_EVIDENCE_STATUS = {
    "unverified": "observed",
    "supported": "checked",
    "verified": "verified",
    "rejected": "invalidated",
    "superseded": "superseded",
}
V1_TO_V2_CLAIM_STATUS_SEED = {
    "unverified": "hypothesis",
    "supported": "supported",
    "verified": "supported",
    "rejected": "contradicted",
    "superseded": "withdrawn",
}

SCHEMA_VERSION = "2.0"


@dataclass
class Evidence:
    id: str
    path: Path
    schema_version: str | None = None
    name: str = ""
    status: str = "proposed"
    source_kind: str = ""
    supports: list[str] = field(default_factory=list)
    contradicts: list[str] = field(default_factory=list)
    supersedes: str | None = None
    superseded_by: str | None = None
    plan: str | None = None
    paper: str | None = None
    raw_artifacts: list[str] = field(default_factory=list)
    runs: list[str] = field(default_factory=list)
    body: str = ""
    raw_frontmatter: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Evidence:
        doc = parse_document(path.read_text(encoding="utf-8"))
        fm = doc.frontmatter
        return cls(
            id=path.stem,
            path=path,
            schema_version=fm.get("schema_version"),
            name=fm.get("name", ""),
            status=fm.get("status", "proposed"),
            source_kind=fm.get("source_kind", ""),
            supports=split_ids(fm.get("supports")),
            contradicts=split_ids(fm.get("contradicts")),
            supersedes=fm.get("supersedes"),
            superseded_by=fm.get("superseded_by"),
            plan=fm.get("plan"),
            paper=fm.get("paper"),
            raw_artifacts=split_ids(fm.get("raw_artifacts")),
            runs=split_ids(fm.get("runs")),
            body=doc.body,
            raw_frontmatter=fm,
        )

    def to_frontmatter(self) -> dict:
        fm = {
            "schema_version": self.schema_version or SCHEMA_VERSION,
            "name": self.name,
            "type": self.raw_frontmatter.get("type") or f"{self.source_kind}-evidence",
            "status": self.status,
            "source_kind": self.source_kind,
            "supports": self.supports,
            "contradicts": self.contradicts,
        }
        if self.supersedes:
            fm["supersedes"] = self.supersedes
        if self.superseded_by:
            fm["superseded_by"] = self.superseded_by
        if self.plan:
            fm["plan"] = self.plan
        if self.paper:
            fm["paper"] = self.paper
        fm["raw_artifacts"] = self.raw_artifacts
        fm["runs"] = self.runs
        for key in ("created_at", "updated_at"):
            if key in self.raw_frontmatter:
                fm[key] = self.raw_frontmatter[key]
        return fm

    def render(self) -> str:
        return render_document(self.to_frontmatter(), self.body)


@dataclass
class Claim:
    id: str
    path: Path
    schema_version: str | None = None
    name: str = ""
    status: str = "hypothesis"
    evidence: list[str] = field(default_factory=list)
    contradicts: list[str] = field(default_factory=list)
    required_evidence: str | None = None
    paper: str | None = None
    body: str = ""
    raw_frontmatter: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Claim:
        doc = parse_document(path.read_text(encoding="utf-8"))
        fm = doc.frontmatter
        return cls(
            id=path.stem,
            path=path,
            schema_version=fm.get("schema_version"),
            name=fm.get("name", ""),
            status=fm.get("status", "hypothesis"),
            evidence=split_ids(fm.get("evidence")),
            contradicts=split_ids(fm.get("contradicts")),
            required_evidence=fm.get("required_evidence"),
            paper=fm.get("paper"),
            body=doc.body,
            raw_frontmatter=fm,
        )

    def statement(self) -> str:
        import re

        match = re.search(r"##\s*Statement\s*\n(.+?)(\n##|\Z)", self.body, re.DOTALL)
        return match.group(1).strip() if match else self.body.strip()

    def to_frontmatter(self) -> dict:
        fm = {
            "schema_version": self.schema_version or SCHEMA_VERSION,
            "name": self.name,
            "type": "research-claim",
            "status": self.status,
            "evidence": self.evidence,
            "contradicts": self.contradicts,
        }
        if self.required_evidence:
            fm["required_evidence"] = self.required_evidence
        if self.paper:
            fm["paper"] = self.paper
        for key in ("created_at", "updated_at"):
            if key in self.raw_frontmatter:
                fm[key] = self.raw_frontmatter[key]
        return fm

    def render(self) -> str:
        return render_document(self.to_frontmatter(), self.body)


@dataclass
class Decision:
    id: str
    path: Path
    schema_version: str | None = None
    name: str = ""
    status: str = "decided"
    evidence: list[str] = field(default_factory=list)
    body: str = ""
    raw_frontmatter: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Decision:
        doc = parse_document(path.read_text(encoding="utf-8"))
        fm = doc.frontmatter
        return cls(
            id=path.stem,
            path=path,
            schema_version=fm.get("schema_version"),
            name=fm.get("name", ""),
            status=fm.get("status", "decided"),
            evidence=split_ids(fm.get("evidence")),
            body=doc.body,
            raw_frontmatter=fm,
        )

    def to_frontmatter(self) -> dict:
        fm = {
            "schema_version": self.schema_version or SCHEMA_VERSION,
            "name": self.name,
            "type": "research-decision",
            "status": self.status,
            "evidence": self.evidence,
        }
        for key in ("created_at", "updated_at"):
            if key in self.raw_frontmatter:
                fm[key] = self.raw_frontmatter[key]
        return fm

    def render(self) -> str:
        return render_document(self.to_frontmatter(), self.body)


def _scan_all(directory: Path, loader) -> tuple[dict, list[tuple[str, str]]]:
    """Returns (valid_items, malformed) — malformed is [(id, reason), ...]
    for a file that exists but couldn't be parsed at all (bad YAML,
    encoding, etc). Mirrors validator.scan_runs: corrupted ledger state is
    data to report, never an exception that kills the validator."""
    items: dict[str, object] = {}
    malformed: list[tuple[str, str]] = []
    if not directory.exists():
        return items, malformed
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith("."):
            continue
        try:
            obj = loader(path)
        except Exception as exc:  # noqa: BLE001 - a malformed record must be reported, never crash validation
            malformed.append((path.stem, str(exc)))
            continue
        items[obj.id] = obj
    return items, malformed


def _load_all(directory: Path, loader) -> dict:
    items, _ = _scan_all(directory, loader)
    return items


def load_evidence(ws) -> dict[str, Evidence]:
    return _load_all(ws.evidence_dir, Evidence.load)


def load_claims(ws) -> dict[str, Claim]:
    return _load_all(ws.claims_dir, Claim.load)


def load_decisions(ws) -> dict[str, Decision]:
    return _load_all(ws.decisions_dir, Decision.load)


def scan_evidence(ws) -> tuple[dict[str, Evidence], list[tuple[str, str]]]:
    return _scan_all(ws.evidence_dir, Evidence.load)


def scan_claims(ws) -> tuple[dict[str, Claim], list[tuple[str, str]]]:
    return _scan_all(ws.claims_dir, Claim.load)


def scan_decisions(ws) -> tuple[dict[str, Decision], list[tuple[str, str]]]:
    return _scan_all(ws.decisions_dir, Decision.load)


# Evidence states strong enough to actually substantiate a claim.
_STRONG_SUPPORT = {"verified"}
_WEAK_SUPPORT = {"checked", "observed"}
_STRONG_CONTRADICTION = {"verified", "checked"}


def recompute_claim_status(claim: Claim, evidence_map: dict[str, Evidence]) -> str:
    """Deterministically derive what a claim's status *should* be from its
    evidence, ignoring superseded evidence. `withdrawn` is manual-only (a
    human/agent decision to retire a claim) and is never produced here —
    if the claim is already withdrawn, recomputation leaves it alone.

    This is the guard against "a claim is not verified merely because one
    experiment supports it": only evidence.status == 'verified' counts as
    strong support, and any live (non-superseded), at-least-'checked'
    contradiction pulls the claim back to 'mixed' or 'contradicted'.
    """
    if claim.status == "withdrawn":
        return "withdrawn"

    def _live(ids: list[str]) -> list[Evidence]:
        return [evidence_map[e] for e in ids if e in evidence_map and evidence_map[e].status != "superseded"]

    supporting = _live(claim.evidence)
    contradicting = _live(claim.contradicts)

    strong_support = any(e.status in _STRONG_SUPPORT for e in supporting)
    weak_support = any(e.status in _WEAK_SUPPORT for e in supporting)
    strong_contradiction = any(e.status in _STRONG_CONTRADICTION for e in contradicting)

    if strong_contradiction and (strong_support or weak_support):
        return "mixed"
    if strong_contradiction:
        return "contradicted"
    if strong_support:
        return "supported"
    if weak_support:
        return "provisional"
    return "hypothesis"
