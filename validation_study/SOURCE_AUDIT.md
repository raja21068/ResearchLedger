# Historical-source audit

All **13 semantic-replay revisions** were checked against public GitHub repository metadata on 2026-09-23. This audit verifies revision identity and changed-file sets; it does **not** verify the authored dependency graph or downstream claim impact.

| Case | Repository | Revision | Date | Changed files |
|---|---|---|---:|---:|
| RH01_POP_TOOLS_SAMPLE_OVERLAP_DEFAULT | `qlu-lab/POP-TOOLS` | `e5e3c9281e93` — Update POP-GWAS.py | 2025-09-02 | 1 |
| RH02_SCANPY_SPARSE_NORMALIZE_TOTAL | `scverse/scanpy` | `8f76101f14b8` — fix: use the non-zero median as `target_sum` on the sparse path (#4256) | 2026-07-27 | 3 |
| RH03_SCANPY_HARMONY_DEFAULTS | `scverse/scanpy` | `2f3bdd263ef0` — perf: update harmony defaults (#4290) | 2026-08-13 | 2 |
| RH04_SQUIDPY_GEARY_VARIANCE | `scverse/squidpy` | `40307c8885e5` — Use Geary's C normality variance in spatial_autocorr (fixes #1183) (#1197) | 2026-06-19 | 3 |
| RH05_TABPFN_PRIOR_SHIFT | `PriorLabs/TabPFN` | `12862a5723d3` — Correct the target prior shift of majority_downsample row subsampling (#1270) | 2026-09-17 | 10 |
| RH06_TABPFN_FEATURE_SUBSAMPLING | `PriorLabs/TabPFN` | `02a9978acfd5` — Fix importance-based feature subsampling never sharing pools across estimators (#1141) | 2026-09-02 | 3 |
| RH07_SAELENS_SEQUENCE_BOUNDARY | `decoderesearch/SAELens` | `964025a2bc49` — fix: preserve sequence starts at batch boundaries (#733) | 2026-09-11 | 2 |
| RH08_COMPASS_PENALTY_PCA | `YosefLab/Compass` | `b0cc0bae420d` — Fixed a bug in penalties (fixed a bad copy paste from microcluster code) | 2021-04-05 | 2 |
| RH09_SCVI_DUPLICATED_PBMC_BATCH | `scverse/scvi-tools` | `f20be750893b` — fix(data): drop duplicated cd4_t_helper batch in purified_pbmc_dataset (#3985) | 2026-09-02 | 3 |
| RH10_SEURAT_NFEATURES_DEFAULT | `satijalab/seurat` | `a61cd8b12242` — Fix default for nfeatures parameter in FindSpatiallyVariableFeatures.Assay | 2026-09-09 | 1 |
| RH11_SQUIDPY_PERMUTATION_NJOBS | `scverse/squidpy` | `8dd3bf4ee5b0` — Fix: seed sequence permutation tests and make results independent of n_jobs (#1234) | 2026-07-06 | 12 |
| RH12_SKLEARN_SPARSE_QUANTILE_SUBSAMPLING | `scikit-learn/scikit-learn` | `cfb297760913` — FIX: Fix `QuantileTransformer(ignore_implicit_zeros=True)` sub-sampling behavior (#32587) | 2026-09-07 | 3 |
| RH13_SAELENS_ZERO_BOS | `decoderesearch/SAELens` | `48c0ea92aac5` — fix: treat a BOS token id of 0 as set when concatenation is disabled (#724) | 2026-08-29 | 2 |

The first ten cases also have authored structural source-case graphs used by the development pilot. RH11–RH13 were added to broaden the **semantic replay** and blind-annotation materials; they are not used to increase the structural pilot sample size.
