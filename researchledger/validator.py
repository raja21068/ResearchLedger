"""The deterministic integrity validator: `researchledger validate`.

Every finding carries a stable RL-code (researchledger/codes.py) so error
messages are greppable and documented, not free text. Checks, in order:
schema validity, id well-formedness, bidirectional claim/evidence
relationships, broken graph edges, run existence, artifact hash
verification, supersession consistency, graph-shape constraints (an
empirical claim needs evidence; experimental evidence needs a run; a run an
evidence relies on needs to have actually succeeded), status drift (recorded
vs recomputed), reproduction information, and manuscript provenance.

Severity is fixed per check, but `--strict` promotes a fixed set of
warning-level codes (codes.STRICT_ESCALATES) to build-failing errors — see
ValidationResult.effective_errors.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import codes
from .environment import environment_digest as compute_environment_digest
from .hashing import sha256_file, sha256_path
from .frontmatter import split_ids
from .models import recompute_claim_status, scan_claims, scan_decisions, scan_evidence
from .schema_validation import validate_instance
from .workspace import Workspace

ID_PATTERNS = {
    "evidence": re.compile(r"^E\d{3}$"),
    "claim": re.compile(r"^C\d{3}$"),
    "decision": re.compile(r"^D\d{3}$"),
    "run": re.compile(r"^R\d{4}$"),
}

# `<!-- rl:claim=C014 -->` or `<!-- rl: claim=C014 evidence=E031,E034 -->`
PROVENANCE_RE = re.compile(
    r"<!--\s*rl:\s*claim=(?P<claims>[\w,\s]+?)(?:\s+evidence=(?P<evidence>[\w,\s]+?))?\s*-->"
)

_RUN_BACKING_STATUSES = {"checked", "verified"}


@dataclass
class Issue:
    level: str  # "error" | "warning"
    code: str
    message: str


@dataclass
class ValidationResult:
    counts: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    def effective_errors(self, strict: bool = False) -> list[Issue]:
        if not strict:
            return self.errors
        return [i for i in self.issues if i.level == "error" or i.code in codes.STRICT_ESCALATES]

    def effective_warnings(self, strict: bool = False) -> list[Issue]:
        if not strict:
            return self.warnings
        return [i for i in self.issues if i.level == "warning" and i.code not in codes.STRICT_ESCALATES]

    def passed(self, strict: bool = False) -> bool:
        return not self.effective_errors(strict)


def scan_runs(ws: Workspace) -> tuple[dict[str, dict], list[tuple[str, str]]]:
    """Returns (valid_runs, malformed) — malformed is [(run_id, reason), ...]
    for a manifest.json that exists but couldn't be parsed at all. Corrupted
    ledger state must never just disappear — see RL004."""
    runs: dict[str, dict] = {}
    malformed: list[tuple[str, str]] = []
    if not ws.runs_dir.exists():
        return runs, malformed
    for run_dir in sorted(ws.runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            runs[run_dir.name] = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            malformed.append((run_dir.name, str(exc)))
    return runs, malformed


def list_runs(ws: Workspace) -> dict[str, dict]:
    """Valid runs only — used by callers (indexer, validate-paper) that just
    need the data and aren't themselves reporting integrity issues. The
    validator uses `scan_runs` directly so a malformed manifest is reported,
    not silently dropped."""
    runs, _ = scan_runs(ws)
    return runs


def list_papers(ws: Workspace) -> list[Path]:
    if not ws.papers_dir.exists():
        return []
    return sorted(ws.papers_dir.glob("*/paper.md"))


def _pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 100.0
    return round(numerator / denominator * 100, 1)


def _safe_artifact_path(run_dir: Path, relative: str) -> Path | None:
    """Resolves a manifest-declared artifact path and refuses anything that
    escapes `run_dir` (a hand-edited manifest could otherwise point the
    validator at `../../etc/passwd`) or that is itself a symlink — a
    high-integrity ledger doesn't follow links it didn't create. Returns
    `None` if the path is unsafe, rather than raising."""
    candidate = run_dir / relative
    if candidate.is_symlink():
        return None
    try:
        resolved = candidate.resolve(strict=False)
        resolved_root = run_dir.resolve(strict=False)
    except OSError:
        return None
    if not resolved.is_relative_to(resolved_root):
        return None
    return resolved


def validate(ws: Workspace) -> ValidationResult:
    result = ValidationResult()
    evidence, malformed_evidence = scan_evidence(ws)
    claims, malformed_claims = scan_claims(ws)
    decisions, malformed_decisions = scan_decisions(ws)
    runs, malformed_runs = scan_runs(ws)

    result.counts = {
        "claims": len(claims),
        "evidence": len(evidence),
        "runs": len(runs),
        "decisions": len(decisions),
    }

    def error(code: str, message: str) -> None:
        result.issues.append(Issue("error", code, message))

    def warning(code: str, message: str) -> None:
        result.issues.append(Issue("warning", code, message))

    # --- Malformed records: reported, never silently dropped or crashed on -
    for rid, reason in malformed_runs:
        error(codes.RL004_MALFORMED_RUN_MANIFEST, f"{rid}/manifest.json could not be parsed: {reason}")
    for eid, reason in malformed_evidence:
        error(codes.RL005_MALFORMED_RECORD, f"{eid}.md could not be parsed: {reason}")
    for cid, reason in malformed_claims:
        error(codes.RL005_MALFORMED_RECORD, f"{cid}.md could not be parsed: {reason}")
    for did, reason in malformed_decisions:
        error(codes.RL005_MALFORMED_RECORD, f"{did}.md could not be parsed: {reason}")

    # --- Schema validity (also covers status-vocabulary validity) --------
    for eid, ev in evidence.items():
        for msg in validate_instance("evidence", ev.raw_frontmatter):
            error(codes.RL003_SCHEMA_INVALID, f"{eid}: {msg}")
    for cid, cl in claims.items():
        for msg in validate_instance("claim", cl.raw_frontmatter):
            error(codes.RL003_SCHEMA_INVALID, f"{cid}: {msg}")
    for did, dec in decisions.items():
        for msg in validate_instance("decision", dec.raw_frontmatter):
            error(codes.RL003_SCHEMA_INVALID, f"{did}: {msg}")
    for rid, manifest in runs.items():
        for msg in validate_instance("run", manifest):
            error(codes.RL003_SCHEMA_INVALID, f"{rid}: {msg}")

    # --- ID well-formedness ------------------------------------------------
    for cid in claims:
        if not ID_PATTERNS["claim"].match(cid):
            error(codes.RL001_BAD_ID, f"{cid} is not a well-formed claim id")
    for eid in evidence:
        if not ID_PATTERNS["evidence"].match(eid):
            error(codes.RL001_BAD_ID, f"{eid} is not a well-formed evidence id")
    for did in decisions:
        if not ID_PATTERNS["decision"].match(did):
            error(codes.RL001_BAD_ID, f"{did} is not a well-formed decision id")
    for rid in runs:
        if not ID_PATTERNS["run"].match(rid):
            error(codes.RL001_BAD_ID, f"{rid} is not a well-formed run id")

    # --- Bidirectional claim/evidence relationships + broken graph edges --
    xref_checks = 0
    xref_ok = 0

    def _claim_support_ids(cl):
        ordered = list(cl.evidence)
        for group in cl.support_sets:
            ordered.extend(group)
        ordered.extend(split_ids(cl.required_evidence))
        # stable de-duplication keeps metrics from double-counting an evidence id
        # that appears in both the legacy flat list and a support set.
        return list(dict.fromkeys(ordered))

    for cid, cl in claims.items():
        for eid in _claim_support_ids(cl):
            xref_checks += 1
            if eid not in evidence:
                error(codes.RL101_BROKEN_EDGE, f"{cid} references nonexistent evidence {eid}")
                continue
            if cid in evidence[eid].supports:
                xref_ok += 1
            else:
                warning(
                    codes.RL102_ASYMMETRIC_EDGE,
                    f"{cid} lists {eid} as evidence, but {eid} does not list {cid} in supports",
                )
        for eid in cl.contradicts:
            xref_checks += 1
            if eid not in evidence:
                error(codes.RL101_BROKEN_EDGE, f"{cid} references nonexistent contradicting evidence {eid}")
                continue
            if cid in evidence[eid].contradicts:
                xref_ok += 1
            else:
                warning(
                    codes.RL102_ASYMMETRIC_EDGE,
                    f"{cid} lists {eid} as contradicting, but {eid} does not list {cid} back",
                )

    for eid, ev in evidence.items():
        for cid in ev.supports:
            xref_checks += 1
            if cid not in claims:
                error(codes.RL101_BROKEN_EDGE, f"{eid} supports nonexistent claim {cid}")
                continue
            if eid in _claim_support_ids(claims[cid]):
                xref_ok += 1
            else:
                warning(
                    codes.RL102_ASYMMETRIC_EDGE,
                    f"{eid} supports {cid}, but {cid} does not list {eid} in evidence",
                )
        for cid in ev.contradicts:
            xref_checks += 1
            if cid not in claims:
                error(codes.RL101_BROKEN_EDGE, f"{eid} contradicts nonexistent claim {cid}")
                continue
            if eid in claims[cid].contradicts:
                xref_ok += 1
            else:
                warning(
                    codes.RL102_ASYMMETRIC_EDGE,
                    f"{eid} contradicts {cid}, but {cid} does not list {eid} back",
                )
        for rid in ev.runs:
            if rid not in runs:
                error(codes.RL101_BROKEN_EDGE, f"{eid} references nonexistent run {rid}")

    for did, dec in decisions.items():
        for eid in dec.evidence:
            if eid not in evidence:
                error(codes.RL101_BROKEN_EDGE, f"{did} references nonexistent evidence {eid}")

    # --- Run identity, artifact/input/metrics/environment integrity ---------
    artifact_total = 0
    artifact_ok = 0
    for rid, manifest in runs.items():
        run_dir = ws.runs_dir / rid

        if manifest.get("run_id") != rid:
            error(
                codes.RL006_MANIFEST_IDENTITY_MISMATCH,
                f"{rid}/manifest.json claims run_id={manifest.get('run_id')!r}, not {rid!r}",
            )

        if not manifest.get("environment"):
            warning(codes.RL210_ENVIRONMENT_MISSING, f"{rid} has no recorded environment")
        else:
            env_path = run_dir / manifest["environment"]
            if not env_path.exists():
                error(codes.RL216_MISSING_ENVIRONMENT_FILE, f"{rid}'s {manifest['environment']} is missing on disk")
            elif manifest.get("environment_digest"):
                try:
                    actual_env = json.loads(env_path.read_text(encoding="utf-8"))
                    actual_digest = compute_environment_digest(actual_env)
                except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                    actual_digest = None
                if actual_digest != manifest["environment_digest"]:
                    error(
                        codes.RL217_ENVIRONMENT_DIGEST_MISMATCH,
                        f"{rid}'s {manifest['environment']} no longer matches its recorded environment_digest",
                    )

        if manifest.get("metrics"):
            metrics_path = run_dir / manifest["metrics"]
            if not metrics_path.exists():
                error(codes.RL214_MISSING_METRICS_FILE, f"{rid}'s {manifest['metrics']} is missing on disk")
            elif manifest.get("metrics_sha256") and sha256_file(metrics_path) != manifest["metrics_sha256"]:
                error(
                    codes.RL215_METRICS_HASH_MISMATCH,
                    f"{rid}'s {manifest['metrics']} no longer matches its recorded hash "
                    f"— the run's scientific result may have been altered",
                )

        for artifact in manifest.get("artifacts", []):
            artifact_total += 1
            safe_path = _safe_artifact_path(run_dir, artifact["path"])
            if safe_path is None:
                error(
                    codes.RL203_UNSAFE_PATH,
                    f"{rid} artifact {artifact['path']} escapes the run directory or is a symlink "
                    f"— refusing to hash it",
                )
                continue
            if not safe_path.exists():
                error(codes.RL201_MISSING_ARTIFACT, f"{rid} artifact {artifact['path']} is missing on disk")
                continue
            if sha256_file(safe_path) != artifact.get("sha256"):
                error(codes.RL202_HASH_MISMATCH, f"{rid} artifact {artifact['path']} hash does not match manifest")
            else:
                artifact_ok += 1
        for dataset in manifest.get("inputs", []):
            input_path_str = dataset["path"]
            input_path = Path(input_path_str)
            if not input_path.is_absolute():
                input_path = Path(manifest.get("working_directory", ".")) / input_path
                if not input_path.is_absolute():
                    input_path = ws.root / input_path
            if not input_path.exists():
                error(codes.RL212_MISSING_INPUT, f"{rid} input {input_path_str} is missing on disk")
                continue
            if sha256_path(input_path) != dataset.get("sha256"):
                error(
                    codes.RL213_INPUT_HASH_MISMATCH,
                    f"{rid} input {input_path_str} no longer matches its recorded hash",
                )

    # --- Tamper-evident run chain --------------------------------------------
    # Seals happen in whatever order `researchledger run` processes finish
    # in, which need not match numeric run-id order under concurrency (see
    # runner.py's module docstring) — so this follows the actual hash
    # pointers each run recorded, rather than assuming sorted(runs) is the
    # seal order. A legacy (pre-chain) run has no `previous_run_hash` key at
    # all and isn't checked for a link; a chain-aware run's link must point
    # at some other run's *current* manifest hash, exactly once each.
    chained = {rid: m for rid, m in runs.items() if "previous_run_hash" in m}
    for rid in runs:
        if rid not in chained:
            warning(codes.RL221_LEGACY_UNCHAINED_RUN, f"{rid} predates the tamper-evident run chain")

    # Built from ALL runs, not just chain-aware ones — a chained run is
    # allowed to point at a *legacy* run's hash (that's exactly how the
    # chain bootstraps when a workspace transitions from unchained to
    # chained), so the lookup a `previous_run_hash` is checked against must
    # include legacy manifests too, or that legitimate link reports as
    # broken.
    current_hash_of: dict[str, str] = {}
    for rid in runs:
        manifest_path = ws.runs_dir / rid / "manifest.json"
        if manifest_path.exists():
            current_hash_of[rid] = "sha256:" + sha256_file(manifest_path)
    hash_to_rid = {h: rid for rid, h in current_hash_of.items()}

    chained_total = len(chained)
    chained_ok = 0
    claimed_by: dict[str, str] = {}  # predecessor hash -> the run id that claims it
    roots_seen = 0
    for rid, manifest in chained.items():
        previous_hash = manifest.get("previous_run_hash")
        if previous_hash is None:
            roots_seen += 1
            if roots_seen > 1:
                error(
                    codes.RL220_CHAIN_BROKEN,
                    f"chain branch detected: {rid} claims to start the chain "
                    f"(previous_run_hash=null), but a chain root already exists",
                )
                continue
            chained_ok += 1
            continue
        if previous_hash not in hash_to_rid:
            error(
                codes.RL220_CHAIN_BROKEN,
                f"{rid}'s previous_run_hash doesn't match any existing run's actual manifest "
                f"— run history may have been altered",
            )
            continue
        if previous_hash in claimed_by:
            error(
                codes.RL220_CHAIN_BROKEN,
                f"chain branch detected: both {claimed_by[previous_hash]} and {rid} claim "
                f"{hash_to_rid[previous_hash]} as their predecessor — the chain must be linear",
            )
            continue
        claimed_by[previous_hash] = rid
        chained_ok += 1

    for eid, ev in evidence.items():
        for rid in ev.runs:
            cited_manifest = runs.get(rid)
            if cited_manifest is not None and cited_manifest.get("exit_code") != 0:
                error(
                    codes.RL211_RUN_FAILED,
                    f"{eid} cites {rid}, which did not complete successfully "
                    f"(exit {cited_manifest.get('exit_code')})",
                )

    # --- Supersession consistency ------------------------------------------
    for eid, ev in evidence.items():
        if ev.supersedes:
            old = evidence.get(ev.supersedes)
            if old is None:
                error(codes.RL101_BROKEN_EDGE, f"{eid} supersedes nonexistent evidence {ev.supersedes}")
            else:
                if old.superseded_by != eid:
                    warning(
                        codes.RL301_SUPERSESSION_MISMATCH,
                        f"{eid} supersedes {ev.supersedes}, but {ev.supersedes}.superseded_by "
                        f"is not {eid}",
                    )
                if old.status != "superseded":
                    warning(
                        codes.RL301_SUPERSESSION_MISMATCH,
                        f"{ev.supersedes} is superseded by {eid} but its status is "
                        f"'{old.status}', not 'superseded'",
                    )
        if ev.superseded_by and ev.superseded_by not in evidence:
            error(codes.RL101_BROKEN_EDGE, f"{eid} superseded_by references nonexistent evidence {ev.superseded_by}")

    # --- Graph-shape constraints: C->E, E_experimental->R, claim basis -----
    for cid, cl in claims.items():
        if cl.status != "hypothesis" and not _claim_support_ids(cl):
            error(codes.RL110_EMPIRICAL_CLAIM_WITHOUT_EVIDENCE, f"{cid} is '{cl.status}' but cites no evidence")

    for eid, ev in evidence.items():
        if ev.source_kind in ("experiment", "computation") and ev.status != "proposed" and not ev.runs:
            error(codes.RL111_EXPERIMENTAL_EVIDENCE_WITHOUT_RUN, f"{eid} ({ev.source_kind}, {ev.status}) cites no run")
        if ev.status in _RUN_BACKING_STATUSES:
            for rid in ev.runs:
                cited_manifest = runs.get(rid)
                if cited_manifest and not cited_manifest.get("artifacts") and not cited_manifest.get("metrics"):
                    warning(
                        codes.RL112_RUN_WITHOUT_ARTIFACT,
                        f"{eid} cites {rid}, which produced neither metrics nor artifacts",
                    )

    for cid, cl in claims.items():
        support_ids = _claim_support_ids(cl)
        if not support_ids:
            continue
        live_supporting = [evidence[e] for e in support_ids if e in evidence and evidence[e].status != "superseded"]
        if live_supporting and all(e.status in ("contradicted", "invalidated") for e in live_supporting):
            error(
                codes.RL120_CLAIM_BASED_ON_REJECTED_EVIDENCE,
                f"{cid}'s only live supporting evidence is contradicted/invalidated",
            )

    # --- Status drift: recorded vs recomputed claim status -----------------
    for cid, cl in claims.items():
        recomputed = recompute_claim_status(cl, evidence)
        if cl.status != recomputed:
            warning(
                codes.RL310_STATUS_DRIFT,
                f"{cid} is recorded as '{cl.status}' but its evidence implies '{recomputed}'",
            )

    # --- Superseded dependency ----------------------------------------------
    for cid, cl in claims.items():
        for eid in _claim_support_ids(cl):
            cited_evidence = evidence.get(eid)
            if cited_evidence and cited_evidence.status == "superseded":
                warning(codes.RL302_SUPERSEDED_DEPENDENCY, f"{cid} depends on superseded evidence {eid}")

    # --- Reproduction information -------------------------------------------
    for eid, ev in evidence.items():
        if ev.runs and "reproduc" not in ev.body.lower():
            warning(codes.RL303_MISSING_REPRODUCTION, f"{eid} has no reproduction command")

    # --- Manuscript provenance ----------------------------------------------
    for paper_path in list_papers(ws):
        text = paper_path.read_text(encoding="utf-8")
        paper_label = f"{paper_path.parent.name}/paper.md"
        for match in PROVENANCE_RE.finditer(text):
            for cid in [c.strip() for c in match.group("claims").split(",") if c.strip()]:
                if cid not in claims:
                    error(codes.RL401_BROKEN_PROVENANCE, f"{paper_label} references nonexistent claim {cid}")
            evidence_group = match.group("evidence") or ""
            for eid in [e.strip() for e in evidence_group.split(",") if e.strip()]:
                if eid not in evidence:
                    error(codes.RL401_BROKEN_PROVENANCE, f"{paper_label} references nonexistent evidence {eid}")

    # --- Metrics -------------------------------------------------------------
    result.metrics["cross_reference_integrity"] = _pct(xref_ok, xref_checks)

    execution_backed = [e for e in evidence.values() if e.source_kind in ("experiment", "computation")]
    run_backed = [e for e in execution_backed if e.runs]
    result.metrics["run_backed_evidence"] = _pct(len(run_backed), len(execution_backed))

    result.metrics["artifact_verification"] = _pct(artifact_ok, artifact_total)

    quantitative_claims = [c for c in claims.values() if re.search(r"\d", c.statement())]
    covered = [
        c
        for c in quantitative_claims
        if any(evidence.get(eid) and evidence[eid].runs and evidence[eid].status == "verified" for eid in c.evidence)
    ]
    result.metrics["quantitative_claim_coverage"] = _pct(len(covered), len(quantitative_claims))

    reproducible_runs = sum(1 for m in runs.values() if m.get("exit_code") == 0 and m.get("git", {}).get("commit"))
    result.metrics["reproducible_runs"] = _pct(reproducible_runs, len(runs))

    result.metrics["chain_integrity"] = _pct(chained_ok, chained_total)

    return result
