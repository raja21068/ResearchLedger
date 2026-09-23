#!/usr/bin/env python3
"""Toolized old/new semantic replay used by the tracked-trajectory harness.

This is intentionally a *proxy* for an executable paper-agent tool.  It exposes
one historical revision case at a time as a deterministic command-line tool,
then writes the selected old/new result into ResearchLedger's artifact and
metrics locations when those environment variables are present.

It must not be described as a Paper2Agent-generated MCP server: the purpose is
to exercise the complete ResearchLedger run -> evidence -> claim -> revision ->
recovery lifecycle before the true external Paper2Agent trajectories are
available.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from run_semantic_replay import CASES
from analysis.expanded_semantic_replay import (
    case_saelens_zero_bos,
    case_sklearn_sparse_quantile,
    case_squidpy_njobs,
)


def _registry() -> dict[str, callable]:
    return {
        "RH01_POP_TOOLS_SAMPLE_OVERLAP_DEFAULT": CASES[0],
        "RH02_SCANPY_SPARSE_NORMALIZE_TOTAL": CASES[1],
        "RH03_SCANPY_HARMONY_DEFAULTS": CASES[2],
        "RH04_SQUIDPY_GEARY_VARIANCE": CASES[3],
        "RH05_TABPFN_PRIOR_SHIFT": CASES[4],
        "RH06_TABPFN_FEATURE_SUBSAMPLING": CASES[5],
        "RH07_SAELENS_SEQUENCE_BOUNDARY": CASES[6],
        "RH08_COMPASS_PENALTY_PCA": CASES[7],
        "RH09_SCVI_DUPLICATED_PBMC_BATCH": CASES[8],
        "RH10_SEURAT_NFEATURES_DEFAULT": CASES[9],
        "RH11_SQUIDPY_PERMUTATION_NJOBS": case_squidpy_njobs,
        "RH12_SKLEARN_SPARSE_QUANTILE_SUBSAMPLING": case_sklearn_sparse_quantile,
        "RH13_SAELENS_ZERO_BOS": case_saelens_zero_bos,
    }


def execute(case_id: str, version: str) -> dict:
    reg = _registry()
    if case_id not in reg:
        raise ValueError(f"unknown case_id: {case_id}")
    row = reg[case_id]()
    key = "old_result" if version == "old" else "new_result"
    return {
        "schema": "researchledger-paper-agent-proxy-output-1",
        "case_id": case_id,
        "repository": row["repository"],
        "base_commit": row["base_commit"],
        "revision_commit": row["revision_commit"],
        "replay_mode": row["replay_mode"],
        "version": version,
        "result": row[key],
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--version", choices=["old", "new"], required=True)
    args = p.parse_args(argv)

    payload = execute(args.case, args.version)
    text = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"

    artifacts_dir = os.environ.get("RESEARCHLEDGER_ARTIFACTS_DIR")
    if artifacts_dir:
        path = Path(artifacts_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / "result.json").write_text(text, encoding="utf-8")

    run_dir = os.environ.get("RESEARCHLEDGER_RUN_DIR")
    if run_dir:
        # Keep metrics deliberately simple and version-independent in schema.
        metrics = {
            "case_id": args.case,
            "version": args.version,
            "result_present": True,
        }
        Path(run_dir, "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
