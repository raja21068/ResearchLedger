#!/usr/bin/env python3
"""Execute additional real-history semantic revision fixtures.

These fixtures intentionally replay only the changed semantics documented by the
historical commits. They do *not* claim full repository or Paper2Agent execution.
Each case includes a mode describing how closely it maps to the upstream code.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from scipy import sparse
import sklearn.preprocessing._data as sk_data

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def squidpy_old_permutations(base: np.ndarray, seed: int, chunks: list[list[int]]) -> dict[int, list[int]]:
    """Replay pre-#1234 chunk-local RNG semantics."""
    out: dict[int, list[int]] = {}
    for chunk in chunks:
        rs = np.random.RandomState(seed + chunk[0])
        clustering = base.copy()
        for p in chunk:
            rs.shuffle(clustering)
            out[p] = clustering.tolist()
    return out


def squidpy_new_permutations(base: np.ndarray, seed: int, chunks: list[list[int]]) -> dict[int, list[int]]:
    """Replay post-#1234 per-permutation SeedSequence semantics."""
    n = sum(len(c) for c in chunks)
    generators = [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(n)]
    out: dict[int, list[int]] = {}
    for chunk in chunks:
        for p in chunk:
            clustering = base.copy()
            generators[p].shuffle(clustering)
            out[p] = clustering.tolist()
    return out


def case_squidpy_njobs() -> dict:
    base = np.arange(12, dtype=np.int64)
    one_worker = [list(range(6))]
    two_worker = [list(range(3)), list(range(3, 6))]
    old_1 = squidpy_old_permutations(base, 42, one_worker)
    old_2 = squidpy_old_permutations(base, 42, two_worker)
    new_1 = squidpy_new_permutations(base, 42, one_worker)
    new_2 = squidpy_new_permutations(base, 42, two_worker)
    old_matches = [old_1[p] == old_2[p] for p in range(6)]
    new_matches = [new_1[p] == new_2[p] for p in range(6)]
    return {
        "case_id": "RH11_SQUIDPY_PERMUTATION_NJOBS",
        "repository": "scverse/squidpy",
        "base_commit": "005c9056fea7c5432fb220abc9b48a384fb8c090",
        "revision_commit": "8dd3bf4ee5b0a0ff789cbf8d346f75d2eb92cdee",
        "source_url": "https://github.com/scverse/squidpy/commit/8dd3bf4ee5b0a0ff789cbf8d346f75d2eb92cdee",
        "replay_mode": "direct-rng-semantics-replay",
        "old_result": {
            "same_seed_one_vs_two_chunks_per_permutation": old_matches,
            "all_permutations_identical_across_chunkings": all(old_matches),
        },
        "new_result": {
            "same_seed_one_vs_two_chunks_per_permutation": new_matches,
            "all_permutations_identical_across_chunkings": all(new_matches),
        },
        "semantic_change_observed": (not all(old_matches)) and all(new_matches),
        "interpretation": (
            "The old chunk-local RandomState makes later permutations depend on how work is split. "
            "The revised SeedSequence design assigns an independent generator to each permutation, "
            "so the same seed yields identical permutation states under one- and two-chunk execution."
        ),
    }


def patched_sparse_fit(self, X, random_state):
    """Exact core semantics introduced by scikit-learn #32587."""
    n_samples, n_features = X.shape
    references = self.references_ * 100
    self.quantiles_ = []
    for feature_idx in range(n_features):
        column_nnz_data = X.data[X.indptr[feature_idx] : X.indptr[feature_idx + 1]]
        if self.subsample is not None and len(column_nnz_data) > self.subsample:
            column_data = np.zeros(shape=self.subsample, dtype=X.dtype)
            column_subsample = (
                self.subsample
                if self.ignore_implicit_zeros
                else self.subsample * len(column_nnz_data) // n_samples
            )
            column_data[:column_subsample] = random_state.choice(
                column_nnz_data, size=column_subsample, replace=False
            )
        else:
            if self.ignore_implicit_zeros:
                column_data = np.zeros(shape=len(column_nnz_data), dtype=X.dtype)
            else:
                column_data = np.zeros(shape=n_samples, dtype=X.dtype)
            column_data[: len(column_nnz_data)] = column_nnz_data
        if not column_data.size:
            self.quantiles_.append([0] * len(references))
        else:
            self.quantiles_.append(np.nanpercentile(column_data, references))
    self.quantiles_ = np.transpose(self.quantiles_)


def case_sklearn_sparse_quantile() -> dict:
    subsample = 500
    n = 2 * subsample**2
    col = np.repeat([0, 1], [subsample - 1, subsample + 1])
    row = np.arange(subsample * 2)
    data = np.concatenate(
        (np.linspace(1, 2, num=subsample - 1), np.linspace(1, 2, num=subsample + 1))
    )
    X = sparse.csc_array((data, (row, col)), shape=(n, 2))

    # Installed sklearn in this runtime still exposes the pre-fix method, so we can
    # execute the old behavior directly, then patch only _sparse_fit with the exact
    # revised logic from commit cfb2977 and execute the same public estimator.
    old_qt = sk_data.QuantileTransformer(
        ignore_implicit_zeros=True, subsample=subsample, n_quantiles=50, random_state=0
    )
    old_qt.fit(X)
    old_quantiles = old_qt.quantiles_.T

    original = sk_data.QuantileTransformer._sparse_fit
    try:
        sk_data.QuantileTransformer._sparse_fit = patched_sparse_fit
        new_qt = sk_data.QuantileTransformer(
            ignore_implicit_zeros=True, subsample=subsample, n_quantiles=50, random_state=0
        )
        new_qt.fit(X)
        new_quantiles = new_qt.quantiles_.T
    finally:
        sk_data.QuantileTransformer._sparse_fit = original

    old_degenerate = bool(np.all(old_quantiles[1] == old_quantiles[1][0]))
    new_degenerate = bool(np.all(new_quantiles[1] == new_quantiles[1][0]))
    return {
        "case_id": "RH12_SKLEARN_SPARSE_QUANTILE_SUBSAMPLING",
        "repository": "scikit-learn/scikit-learn",
        "base_commit": "9bafc1c9cab99aa036aba8207125637c39fd22db",
        "revision_commit": "cfb2977609132206cecb6000b2e0e27a04b5b983",
        "source_url": "https://github.com/scikit-learn/scikit-learn/commit/cfb2977609132206cecb6000b2e0e27a04b5b983",
        "replay_mode": "package-runtime-old-plus-commit-patched-new",
        "old_result": {
            "second_column_degenerate": old_degenerate,
            "second_column_range": float(np.ptp(old_quantiles[1])),
            "old_formula_selected_nonzeros": int(subsample * (subsample + 1) // n),
        },
        "new_result": {
            "second_column_degenerate": new_degenerate,
            "second_column_range": float(np.ptp(new_quantiles[1])),
            "new_formula_selected_nonzeros": subsample,
            "similar_columns_have_similar_quantiles_rtol_0_1": bool(
                np.allclose(new_quantiles[0], new_quantiles[1], rtol=0.1)
            ),
        },
        "semantic_change_observed": old_degenerate and not new_degenerate,
        "interpretation": (
            "On the upstream regression fixture, the pre-fix sparse path chooses zero non-zero "
            "observations for the 501-entry column and yields degenerate quantiles. Patching only "
            "the changed method with the commit logic samples 500 non-zero values and restores a "
            "non-degenerate, column-consistent quantile estimate."
        ),
    }


def sae_disable_concat(
    seqs: list[torch.Tensor],
    context_size: int,
    begin_batch_token_id: int | None,
    *,
    revised: bool,
) -> list[list[int]]:
    begin_sequence_token_id = None
    if revised:
        if begin_batch_token_id is not None and begin_sequence_token_id is None:
            begin_sequence_token_id = begin_batch_token_id
    else:
        if begin_batch_token_id and not begin_sequence_token_id:
            begin_sequence_token_id = begin_batch_token_id

    out: list[list[int]] = []
    for seq in seqs:
        sequence = seq.clone()
        if (
            begin_sequence_token_id is not None
            and len(sequence) >= context_size - 1
            and sequence[0] != begin_sequence_token_id
        ):
            prefix = torch.tensor([begin_sequence_token_id], dtype=torch.long)
            sequence = torch.cat([prefix, sequence[: context_size - 1]])
        if len(sequence) >= context_size:
            out.append(sequence[:context_size].tolist())
    return out


def case_saelens_zero_bos() -> dict:
    all_toks = torch.arange(1, 20)
    seqs = [all_toks[:3], all_toks[3:10], all_toks[10:17], all_toks[17:]]
    old = sae_disable_concat(seqs, 5, 0, revised=False)
    new = sae_disable_concat(seqs, 5, 0, revised=True)
    expected = [[0, 4, 5, 6, 7], [0, 11, 12, 13, 14]]
    return {
        "case_id": "RH13_SAELENS_ZERO_BOS",
        "repository": "decoderesearch/SAELens",
        "base_commit": "78f3db823428bc84e44ac41cada6777f44057436",
        "revision_commit": "48c0ea92aac5b3684d2c4cafd8b8dc3c19c9349a",
        "source_url": "https://github.com/decoderesearch/SAELens/commit/48c0ea92aac5b3684d2c4cafd8b8dc3c19c9349a",
        "replay_mode": "direct-branch-semantics-replay",
        "old_result": old,
        "new_result": new,
        "expected_new_result": expected,
        "semantic_change_observed": old != new and new == expected,
        "interpretation": (
            "Token id 0 is a valid BOS id. The pre-fix truthiness test treats it as absent, so the "
            "emitted chunks begin with data tokens. The revised explicit None check preserves BOS=0."
        ),
    }


def source_diagnostic_pymc_logpow() -> dict:
    # This mirrors the exact numerical failure described in the upstream regression
    # test. It is deliberately not counted as a package-runtime old/new replay because
    # importing this runtime's PyMC stack fails due to an unrelated ArviZ API mismatch.
    a = -800.0
    m = 3.0
    underflowed_x = float(np.exp(a))
    old = float("-inf") if underflowed_x == 0.0 else float(m * np.log(underflowed_x))
    new = m * a  # symbolic log(exp(a)) stabilization in the revised implementation
    return {
        "case_id": "SD01_PYMC_LOGPOW_UNDERFLOW",
        "repository": "pymc-devs/pymc",
        "base_commit": "fddbacb19c91dda2b79fa0d736f3632ec1079708",
        "revision_commit": "fad6a0abbb5b2883920bc9aece37db5df7a5cd14",
        "source_url": "https://github.com/pymc-devs/pymc/commit/fad6a0abbb5b2883920bc9aece37db5df7a5cd14",
        "replay_mode": "source-equivalent-numeric-diagnostic-not-counted",
        "old_result": old,
        "new_result": new,
        "upstream_expected_new": -2400.0,
        "semantic_change_observed": np.isneginf(old) and new == -2400.0,
        "limitation": "PyMC package runtime not executed because the installed PyMC/ArviZ combination is incompatible in this container.",
    }


def main() -> None:
    original_path = RESULTS / "prr_executed_semantic_replay.json"
    original = json.loads(original_path.read_text())
    added = [case_squidpy_njobs(), case_sklearn_sparse_quantile(), case_saelens_zero_bos()]
    combined = list(original["cases"]) + added
    result = {
        "schema": "prr-executed-semantic-replay-2",
        "scope": (
            "Thirteen genuine historical commits with the changed semantics replayed locally. "
            "The first ten are the prior pilot; RH11-RH13 broaden reproducibility, sparse-statistic, "
            "and tokenization failure modes. This remains narrower than full old/new repository + "
            "Paper2Agent re-execution and is not independent human-adjudicated external validation."
        ),
        "n_cases": len(combined),
        "n_semantic_changes_observed": sum(bool(c.get("semantic_change_observed")) for c in combined),
        "repositories": sorted({c["repository"] for c in combined}),
        "n_repositories": len({c["repository"] for c in combined}),
        "cases": combined,
        "supplemental_source_diagnostics": [source_diagnostic_pymc_logpow()],
    }
    out = RESULTS / "prr_executed_semantic_replay_v2.json"
    out.write_text(json.dumps(result, indent=2) + "\n")

    # Human-readable compact table.
    rows = [
        "case_id,repository,replay_mode,semantic_change_observed",
        *[
            f'{c["case_id"]},{c["repository"]},{c["replay_mode"]},{str(bool(c.get("semantic_change_observed"))).lower()}'
            for c in combined
        ],
    ]
    (RESULTS / "prr_executed_semantic_replay_v2_summary.csv").write_text("\n".join(rows) + "\n")
    print(json.dumps({
        "n_cases": result["n_cases"],
        "n_repositories": result["n_repositories"],
        "n_semantic_changes_observed": result["n_semantic_changes_observed"],
        "added": [c["case_id"] for c in added],
    }, indent=2))


if __name__ == "__main__":
    main()
