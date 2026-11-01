"""Prepare a web project's workspace as a Paper Factory / ResearchLedger workspace.

Run as a subprocess (`python -m webapi.app.factory_bridge init <dir>`) so the
heavy Factory imports never load into the API process. It performs the same
steps as `researchctl init` (factory/cli/main.py:init_project) on a directory the
web app already created; `researchctl init` itself refuses existing directories.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def init(workspace: Path) -> dict:
    workspace = workspace.resolve()
    if (workspace / "state.json").is_file():
        return {"status": "ALREADY_INITIALIZED", "workspace": str(workspace)}
    from factory.io import atomic_json
    from factory.science.literature import scaffold_prior_art
    from factory.science.protocol import scaffold as protocol_scaffold
    from factory.state import ProjectState
    from researchledger.workspace import init_workspace

    (workspace / "_inputs").mkdir(parents=True, exist_ok=True)
    init_workspace(workspace)
    context = workspace / "_inputs" / "context.json"
    if not context.is_file():
        atomic_json(context, {"science_mode": "exploration", "ledger_enabled": True,
                              "allow_network_install": False, "code_mode": "agent",
                              "review_agent": "auto"})
    protocol_scaffold(workspace)
    scaffold_prior_art(workspace)
    ProjectState(workspace.name).save(workspace / "state.json")
    return {"status": "INITIALIZED", "workspace": str(workspace)}


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "init":
        print("usage: python -m webapi.app.factory_bridge init <workspace>", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(init(Path(sys.argv[2])), indent=2))
