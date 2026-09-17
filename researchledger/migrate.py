"""`researchledger migrate --from v1 [--dry-run]`: rewrites evidence/claim/
decision frontmatter into the v2 canonical form (real YAML arrays,
schema_version, v2 status vocabulary). Claim status is never blindly
renamed — it's re-derived with `recompute_claim_status` against the
(already-migrated) evidence, since a rename can't tell "supported" from
"mixed" without looking at the evidence graph. Nothing is touched without a
backup first; `--dry-run` reports what *would* change without writing
anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .atomic import atomic_write_json, atomic_write_text
from .frontmatter import parse_document
from .models import (
    SCHEMA_VERSION,
    V1_TO_V2_CLAIM_STATUS_SEED,
    V1_TO_V2_EVIDENCE_STATUS,
    Claim,
    Decision,
    Evidence,
    recompute_claim_status,
)
from .workspace import Workspace


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_v2(frontmatter: dict) -> bool:
    return str(frontmatter.get("schema_version", "")).startswith("2")


@dataclass
class MigrationReport:
    dry_run: bool
    evidence_migrated: int = 0
    claims_migrated: int = 0
    decisions_migrated: int = 0
    already_v2: int = 0
    malformed: list[dict] = field(default_factory=list)
    backup_dir: str | None = None

    def to_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "evidence_migrated": self.evidence_migrated,
            "claims_migrated": self.claims_migrated,
            "decisions_migrated": self.decisions_migrated,
            "already_v2": self.already_v2,
            "malformed": self.malformed,
            "backup_dir": self.backup_dir,
        }


def _backup(ws: Workspace) -> Path | None:
    import shutil
    import uuid

    timestamp = _now().replace(":", "-")
    backup_dir = ws.root / "backup" / f"v1-{timestamp}-{uuid.uuid4().hex[:8]}"
    copied_any = False
    for directory in (ws.evidence_dir, ws.claims_dir, ws.decisions_dir):
        if directory.exists() and any(directory.glob("*.md")):
            dest = backup_dir / directory.relative_to(ws.root)
            shutil.copytree(directory, dest)
            copied_any = True
    return backup_dir if copied_any else None


def migrate_v1_to_v2(ws: Workspace, *, dry_run: bool = False) -> MigrationReport:
    report = MigrationReport(dry_run=dry_run)

    if not dry_run:
        backup_dir = _backup(ws)
        report.backup_dir = str(backup_dir.relative_to(ws.root)) if backup_dir else None

    evidence_objs: dict[str, Evidence] = {}
    for path in sorted(ws.evidence_dir.glob("*.md")) if ws.evidence_dir.exists() else []:
        try:
            fm = parse_document(path.read_text(encoding="utf-8")).frontmatter
        except (OSError, UnicodeDecodeError) as exc:
            report.malformed.append({"path": str(path), "reason": str(exc)})
            continue
        if _is_v2(fm):
            report.already_v2 += 1
            evidence_objs[path.stem] = Evidence.load(path)
            continue
        try:
            ev = Evidence.load(path)
        except Exception as exc:  # noqa: BLE001 - a malformed input file must never abort the batch
            report.malformed.append({"path": str(path), "reason": str(exc)})
            continue
        ev.status = V1_TO_V2_EVIDENCE_STATUS.get(ev.status, ev.status)
        ev.schema_version = SCHEMA_VERSION
        evidence_objs[ev.id] = ev
        if not dry_run:
            atomic_write_text(path, ev.render())
        report.evidence_migrated += 1

    for path in sorted(ws.claims_dir.glob("*.md")) if ws.claims_dir.exists() else []:
        try:
            fm = parse_document(path.read_text(encoding="utf-8")).frontmatter
        except (OSError, UnicodeDecodeError) as exc:
            report.malformed.append({"path": str(path), "reason": str(exc)})
            continue
        if _is_v2(fm):
            report.already_v2 += 1
            continue
        try:
            cl = Claim.load(path)
        except Exception as exc:  # noqa: BLE001
            report.malformed.append({"path": str(path), "reason": str(exc)})
            continue
        cl.status = V1_TO_V2_CLAIM_STATUS_SEED.get(cl.status, "hypothesis")
        cl.status = recompute_claim_status(cl, evidence_objs)
        cl.schema_version = SCHEMA_VERSION
        if not dry_run:
            atomic_write_text(path, cl.render())
        report.claims_migrated += 1

    for path in sorted(ws.decisions_dir.glob("*.md")) if ws.decisions_dir.exists() else []:
        try:
            fm = parse_document(path.read_text(encoding="utf-8")).frontmatter
        except (OSError, UnicodeDecodeError) as exc:
            report.malformed.append({"path": str(path), "reason": str(exc)})
            continue
        if _is_v2(fm):
            report.already_v2 += 1
            continue
        try:
            dec = Decision.load(path)
        except Exception as exc:  # noqa: BLE001
            report.malformed.append({"path": str(path), "reason": str(exc)})
            continue
        dec.schema_version = SCHEMA_VERSION
        if not dry_run:
            atomic_write_text(path, dec.render())
        report.decisions_migrated += 1

    if not dry_run:
        atomic_write_json(ws.root / "migration-report.json", report.to_dict())

    return report


def render(report: MigrationReport) -> str:
    lines = [f"ResearchLedger migration v1 -> v2 {'(dry run)' if report.dry_run else ''}".rstrip()]
    lines.append("")
    lines.append(f"{report.evidence_migrated} evidence record(s) migrated")
    lines.append(f"{report.claims_migrated} claim(s) migrated")
    lines.append(f"{report.decisions_migrated} decision(s) migrated")
    lines.append(f"{report.already_v2} already on schema v2 (untouched)")
    lines.append(f"{len(report.malformed)} file(s) require manual review")
    for entry in report.malformed:
        lines.append(f"  - {entry['path']}: {entry['reason']}")
    if report.backup_dir:
        lines.append("")
        lines.append(f"Backup written to {report.backup_dir}/")
    return "\n".join(lines)
