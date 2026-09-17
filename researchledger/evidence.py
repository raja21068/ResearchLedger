"""`researchledger evidence create`: the one CLI-driven way to add an
evidence record, so a new record is graph-consistent by construction
(correct id, schema_version, bidirectional supports/contradicts edges,
recomputed claim status) instead of relying on the next `validate` pass to
catch a hand-written mistake.

It never sets status above 'checked' when created from a run: a run
completing successfully makes evidence *checked*, not *verified* —
promoting to verified is a separate, deliberate call a human or a skill
makes after independent corroboration, never something automatic. See
reference/run-ledger.md#status-vocabulary.

The claim-existence check, id allocation, and every write (the evidence
file plus each linked claim) all happen under one `ledger_lock` acquisition
— concurrent `evidence create` calls used to race on `next_id`, handing out
the same id to more than one caller and losing whichever file got written
second.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .atomic import atomic_write_text
from .models import Claim, Evidence, load_claims, load_evidence, recompute_claim_status
from .workspace import Workspace, ledger_lock, next_id

_AUTO_ALLOWED_STATUSES = {"proposed", "observed", "checked"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _run_manifest(ws: Workspace, run_id: str) -> dict | None:
    path = ws.runs_dir / run_id / "manifest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def create_evidence(
    ws: Workspace,
    *,
    from_run: str | None = None,
    supports: list[str] | None = None,
    contradicts: list[str] | None = None,
    source_kind: str | None = None,
    status: str = "checked",
    name: str | None = None,
) -> Evidence:
    supports = list(supports or [])
    contradicts = list(contradicts or [])

    if from_run and status not in _AUTO_ALLOWED_STATUSES:
        raise ValueError(
            f"evidence created from a run cannot start at status {status!r} — promoting to "
            f"'verified' is a separate, deliberate step, not something a run's completion earns on its own."
        )

    manifest = None
    if from_run:
        manifest = _run_manifest(ws, from_run)
        if manifest is None:
            raise ValueError(f"No such run: {from_run}")
        if status == "checked" and manifest.get("status") != "completed":
            raise ValueError(
                f"{from_run} did not complete successfully (status={manifest.get('status')!r}) — "
                f"'checked' evidence implies the run's result looks right, which isn't meaningful for "
                f"a failed/timed-out run. Use --status proposed or --status observed instead."
            )

    with ledger_lock(ws):
        existing_claims = load_claims(ws)
        for claim_id in supports + contradicts:
            if claim_id not in existing_claims:
                raise ValueError(f"No such claim: {claim_id} (create it before linking evidence to it)")

        evidence_id = next_id(ws.evidence_dir, "E", 3)
        resolved_source_kind = source_kind or ("experiment" if from_run else "observation")
        resolved_name = name or (f"Result of {from_run}" if from_run else evidence_id)

        body_lines = [f"# Evidence: {resolved_name}", ""]
        if manifest:
            body_lines += ["## Result", ""]
            metrics_name = manifest.get("metrics")
            if metrics_name:
                assert from_run is not None  # manifest is only set when from_run was given
                metrics_path = ws.runs_dir / from_run / metrics_name
                if metrics_path.exists():
                    try:
                        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                        for key, value in metrics.items():
                            body_lines.append(f"- {key} = {value}")
                    except json.JSONDecodeError:
                        pass
            body_lines += ["", "## Reproducibility", "", f"researchledger reproduce {from_run}", ""]

        evidence = Evidence(
            id=evidence_id,
            path=ws.evidence_dir / f"{evidence_id}.md",
            schema_version="2.0",
            name=resolved_name,
            status=status,
            source_kind=resolved_source_kind,
            supports=supports,
            contradicts=contradicts,
            runs=[from_run] if from_run else [],
            body="\n".join(body_lines) + "\n",
            raw_frontmatter={"created_at": _now(), "updated_at": _now()},
        )
        atomic_write_text(evidence.path, evidence.render())

        evidence_map = load_evidence(ws)
        for claim_id in supports + contradicts:
            claim = Claim.load(ws.claims_dir / f"{claim_id}.md")
            target_list = claim.evidence if claim_id in supports else claim.contradicts
            if evidence_id not in target_list:
                target_list.append(evidence_id)
            claim.status = recompute_claim_status(claim, evidence_map)
            atomic_write_text(claim.path, claim.render())

    return evidence
