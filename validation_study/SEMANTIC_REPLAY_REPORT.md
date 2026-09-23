# Executed semantic replay of historical PRR revisions

## Scope

This run executes the smallest semantic unit changed by each of the ten historical commits. It is **not** a full checkout/install/Paper2Agent regeneration study, and it does not use independent human adjudication. It upgrades the earlier graph-only pilot by demonstrating that each selected historical change is behaviorally, numerically, or configuration-semantically observable on a concrete fixture.

**Result: 10/10 fixtures exhibited the expected old/new semantic difference.**

| Case | Repository | Replay mode | Change observed | Key result |
|---|---|---|---:|---|
| RH01_POP_TOOLS_SAMPLE_OVERLAP_DEFAULT | `qlu-lab/POP-TOOLS` | direct-argument-semantics | yes | old/new behavior differs as documented |
| RH02_SCANPY_SPARSE_NORMALIZE_TOTAL | `scverse/scanpy` | numeric-formula-replay | yes | target sum 15.0 → 20.0 |
| RH03_SCANPY_HARMONY_DEFAULTS | `scverse/scanpy` | configuration-replay | yes | old/new behavior differs as documented |
| RH04_SQUIDPY_GEARY_VARIANCE | `scverse/squidpy` | numeric-formula-replay | yes | analytic p 0.04438 → 0.02092 |
| RH05_TABPFN_PRIOR_SHIFT | `PriorLabs/TabPFN` | numeric-prior-correction-replay | yes | class-1 probability 0.700 → 0.206 |
| RH06_TABPFN_FEATURE_SUBSAMPLING | `PriorLabs/TabPFN` | numeric-feature-coverage-replay | yes | feature coverage 9 → 12 / 12 |
| RH07_SAELENS_SEQUENCE_BOUNDARY | `decoderesearch/SAELens` | direct-code-replay | yes | old/new behavior differs as documented |
| RH08_COMPASS_PENALTY_PCA | `YosefLab/Compass` | direct-expression-replay | yes | old error → new ok |
| RH09_SCVI_DUPLICATED_PBMC_BATCH | `scverse/scvi-tools` | loader-filter-semantics-replay | yes | rows 33 → 30 in surrogate fixture |
| RH10_SEURAT_NFEATURES_DEFAULT | `satijalab/seurat` | source-level-configuration-replay | yes | old/new behavior differs as documented |

## Interpretation

This run provides **executed historical-semantic evidence**, not end-to-end paper-agent evidence. The strongest cases are RH02 (numerical normalization), RH04 (analytic p-value), RH05 (probability calibration), RH06 (feature coverage), RH07 (tokenization boundary), and RH08 (runtime error versus valid PCA setup). RH03 and RH10 are configuration/default changes; RH09 executes the exact filtering predicate on a surrogate batch table rather than downloading the original H5AD.

For a high-level-journal external-validation claim, the remaining requirements are: full old/new repository execution, Paper2Agent generation or equivalent tool freezing, independent blind dependency/impact annotation, and repository-clustered uncertainty over a substantially larger revision sample.
