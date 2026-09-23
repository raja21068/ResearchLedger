"""Transactional evidence-revision planning and application.

This module adds the missing *revision-time* operation to ResearchLedger's
existing immutable run/provenance ledger.  A revision is deliberately narrow:
it changes one or more evidence states, deterministically recomputes dependent
claim states (including v2.1 support-set semantics), and commits the resulting
multi-file change under the workspace ledger lock.

The transaction protocol is application-level rather than filesystem-magic:
we verify optimistic-concurrency hashes, persist exact pre-images under
``.researchledger/revisions/<txid>/before/``, write a ``prepared`` journal,
atomically replace each ledger file, run the deterministic validator, then mark
``committed``.  Any exception restores every pre-image and marks the journal
``rolled_back``.  A later revision first recovers any transaction left in a
nonterminal phase by a process crash.
"""
from __future__ import annotations

import copy
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .atomic import atomic_write_json, atomic_write_text
from .hashing import sha256_file
from .models import EVIDENCE_STATUSES, load_claims, load_evidence, recompute_claim_status
from .validator import validate
from .workspace import Workspace, ledger_lock


class RevisionError(RuntimeError):
    pass


class RevisionConflict(RevisionError):
    pass


@dataclass
class EntityChange:
    entity_id: str
    before: str
    after: str


@dataclass
class RevisionPlan:
    evidence_updates: dict[str, str]
    evidence_changes: list[EntityChange] = field(default_factory=list)
    claim_changes: list[EntityChange] = field(default_factory=list)
    base_hashes: dict[str, str] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "evidence_updates": self.evidence_updates,
            "evidence_changes": [asdict(x) for x in self.evidence_changes],
            "claim_changes": [asdict(x) for x in self.claim_changes],
            "base_hashes": self.base_hashes,
            "reason": self.reason,
        }


def _rel(ws: Workspace, path: Path) -> str:
    return path.resolve().relative_to(ws.root.resolve()).as_posix()


def _hash(path: Path) -> str:
    return "sha256:" + sha256_file(path)


def plan_evidence_revision(ws: Workspace, updates: dict[str, str], *, reason: str = "") -> RevisionPlan:
    """Plan a revision without mutating the workspace."""
    if not updates:
        raise ValueError("revision requires at least one E###=status update")
    evidence = load_evidence(ws)
    claims = load_claims(ws)
    revised = copy.deepcopy(evidence)

    plan = RevisionPlan(evidence_updates=dict(updates), reason=reason)
    for eid, new_status in updates.items():
        if eid not in evidence:
            raise ValueError(f"unknown evidence id: {eid}")
        if new_status not in EVIDENCE_STATUSES:
            raise ValueError(f"invalid evidence status {new_status!r}; expected one of {sorted(EVIDENCE_STATUSES)}")
        old_status = evidence[eid].status
        if old_status != new_status:
            plan.evidence_changes.append(EntityChange(eid, old_status, new_status))
            revised[eid].status = new_status
        plan.base_hashes[_rel(ws, evidence[eid].path)] = _hash(evidence[eid].path)

    # Claim status is a deterministic derived state; recompute every claim so
    # indirect support-set changes cannot be silently missed.
    for cid, claim in claims.items():
        after = recompute_claim_status(claim, revised)
        if claim.status != after:
            plan.claim_changes.append(EntityChange(cid, claim.status, after))
            plan.base_hashes[_rel(ws, claim.path)] = _hash(claim.path)
    return plan


def _tx_root(ws: Workspace) -> Path:
    return ws.root / ".researchledger" / "revisions"


def _write_manifest(tx_dir: Path, payload: dict) -> None:
    atomic_write_json(tx_dir / "manifest.json", payload)


def _restore_transaction(ws: Workspace, tx_dir: Path, manifest: dict) -> None:
    for rel in manifest.get("files", []):
        backup = tx_dir / "before" / rel
        target = ws.root / rel
        if backup.exists():
            atomic_write_text(target, backup.read_text(encoding="utf-8"))
    manifest["phase"] = "rolled_back"
    manifest["rolled_back_at"] = time.time()
    _write_manifest(tx_dir, manifest)


def recover_incomplete_revisions(ws: Workspace) -> list[str]:
    """Restore any transaction that was prepared/applying when a process died."""
    root = _tx_root(ws)
    recovered: list[str] = []
    if not root.exists():
        return recovered
    for tx_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        mp = tx_dir / "manifest.json"
        if not mp.exists():
            continue
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if m.get("phase") in {"prepared", "applying"}:
            _restore_transaction(ws, tx_dir, m)
            recovered.append(tx_dir.name)
    return recovered


def apply_evidence_revision(ws: Workspace, updates: dict[str, str], *, reason: str = "") -> dict:
    """Plan and commit an evidence revision, rolling back on conflict or validation failure."""
    with ledger_lock(ws):
        recovered = recover_incomplete_revisions(ws)
        plan = plan_evidence_revision(ws, updates, reason=reason)

        # Optimistic freshness check.  This is mostly defensive while the lock is
        # held, but it also catches a stale externally serialized plan/workspace.
        for rel, expected in plan.base_hashes.items():
            path = ws.root / rel
            if not path.exists() or _hash(path) != expected:
                raise RevisionConflict(f"stale revision base: {rel} changed since planning")

        # Refuse to hide pre-existing integrity failures inside a revision.
        before_validation = validate(ws)
        if before_validation.errors:
            raise RevisionError(
                "workspace has pre-existing validation errors; repair them before applying a revision"
            )

        evidence = load_evidence(ws)
        claims = load_claims(ws)
        revised_evidence = copy.deepcopy(evidence)
        for eid, status in updates.items():
            revised_evidence[eid].status = status
        for ch in plan.claim_changes:
            claims[ch.entity_id].status = ch.after

        changed_paths: dict[str, str] = {}
        for ch in plan.evidence_changes:
            obj = revised_evidence[ch.entity_id]
            changed_paths[_rel(ws, obj.path)] = obj.render()
        for ch in plan.claim_changes:
            obj = claims[ch.entity_id]
            changed_paths[_rel(ws, obj.path)] = obj.render()

        txid = time.strftime("REV%Y%m%dT%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
        tx_dir = _tx_root(ws) / txid
        tx_dir.mkdir(parents=True, exist_ok=False)
        files = sorted(changed_paths)
        for rel in files:
            src = ws.root / rel
            backup = tx_dir / "before" / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

        manifest = {
            "schema": "researchledger-revision-1",
            "txid": txid,
            "phase": "prepared",
            "created_at": time.time(),
            "reason": reason,
            "files": files,
            "plan": plan.to_dict(),
            "recovered_before_apply": recovered,
        }
        _write_manifest(tx_dir, manifest)

        try:
            manifest["phase"] = "applying"
            _write_manifest(tx_dir, manifest)
            for rel in files:
                atomic_write_text(ws.root / rel, changed_paths[rel])

            after_validation = validate(ws)
            if after_validation.errors:
                first = "; ".join(f"{i.code}: {i.message}" for i in after_validation.errors[:3])
                raise RevisionError(f"revision violates ledger invariants: {first}")

            manifest["phase"] = "committed"
            manifest["committed_at"] = time.time()
            manifest["after_hashes"] = {rel: _hash(ws.root / rel) for rel in files}
            _write_manifest(tx_dir, manifest)
            return {
                "txid": txid,
                "status": "committed",
                "reason": reason,
                "evidence_changes": [asdict(x) for x in plan.evidence_changes],
                "claim_changes": [asdict(x) for x in plan.claim_changes],
                "files": files,
                "recovered_before_apply": recovered,
            }
        except Exception:
            _restore_transaction(ws, tx_dir, manifest)
            raise
