"""Workspace discovery and the on-disk layout the run ledger reads/writes.

A workspace is recognized independently of the higher-level ResearchLedger skills:
any of `project.md`, `research-state.md`, a `research/` directory, or a
`.researchledger` marker file is enough. This lets `researchledger` be used
standalone (e.g. in CI) in a directory that only ever ran `researchledger
init`, without requiring the `/research` skill to have run first.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .atomic import file_lock

_MARKERS = ("project.md", "research-state.md", "research", ".researchledger")


class WorkspaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def project_file(self) -> Path:
        return self.root / "project.md"

    @property
    def state_file(self) -> Path:
        return self.root / "research-state.md"

    @property
    def research_dir(self) -> Path:
        return self.root / "research"

    @property
    def evidence_dir(self) -> Path:
        return self.research_dir / "evidence"

    @property
    def claims_dir(self) -> Path:
        return self.research_dir / "claims"

    @property
    def decisions_dir(self) -> Path:
        return self.research_dir / "decisions"

    @property
    def runs_dir(self) -> Path:
        return self.research_dir / "runs"

    @property
    def plans_dir(self) -> Path:
        return self.root / "plans"

    @property
    def papers_dir(self) -> Path:
        return self.root / "papers"

    def is_workspace(self) -> bool:
        return any((self.root / marker).exists() for marker in _MARKERS)


def find_workspace(start: Path | None = None) -> Workspace:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if any((candidate / marker).exists() for marker in _MARKERS):
            return Workspace(candidate)
    raise WorkspaceError(
        "No ResearchLedger workspace found in this directory or any parent "
        "(looked for project.md, research-state.md, research/, .researchledger). "
        "Run 'researchledger init' first."
    )


def init_workspace(start: Path | None = None) -> Workspace:
    root = (start or Path.cwd()).resolve()
    ws = Workspace(root)
    for directory in (ws.evidence_dir, ws.claims_dir, ws.decisions_dir, ws.runs_dir):
        directory.mkdir(parents=True, exist_ok=True)
    # `.researchledger/` is a directory, not a file: it doubles as a
    # workspace marker and as the home for index.json (see indexer.py).
    (root / ".researchledger").mkdir(parents=True, exist_ok=True)
    return ws


@contextmanager
def ledger_lock(ws: Workspace, *, timeout: float = 30.0) -> Iterator[None]:
    """The one workspace-wide lock for anything that mutates the graph:
    allocating a run/evidence id, sealing a run's manifest (and updating the
    chain tip), or writing evidence + updating the claims it links to. A
    single lock file, held only for the critical section itself — command
    *execution* in `researchledger run` happens entirely outside it, so
    concurrent runs still execute in parallel; only the bookkeeping that
    must be serialized (id allocation, chain-tip update, multi-file writes)
    actually blocks on this.
    """
    lock_dir = ws.root / ".researchledger"
    lock_dir.mkdir(parents=True, exist_ok=True)
    with file_lock(lock_dir / "ledger", timeout=timeout):
        yield


def next_id(directory: Path, prefix: str, width: int) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)}(\d{{{width}}})")
    highest = 0
    if directory.exists():
        for entry in directory.iterdir():
            match = pattern.match(entry.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return f"{prefix}{highest + 1:0{width}d}"
