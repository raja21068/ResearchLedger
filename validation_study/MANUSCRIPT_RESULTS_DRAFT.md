# Manuscript-ready results language for the current development evidence

## Historical-semantic replay

We assembled 13 genuine historical semantic revisions spanning nine scientific-software repositories and replayed the smallest changed semantic unit on controlled fixtures. All 13 produced the expected old/new behavioral, numerical, reproducibility, or configuration-level difference. The cases include sparse-normalization and sparse-quantile corrections, Geary's C analytic variance, probability calibration after class downsampling, feature-subsampling coverage, permutation reproducibility across work partitioning, sequence-boundary/BOS handling, removal of a duplicated PBMC batch, and scientific-default changes. These replays establish that the selected historical revisions are semantically consequential on the tested fixtures; they are not full repository-level or paper-agent re-executions.

For RH04, the corrected Geary variance changes the fixture's analytic p-value from approximately 0.0444 to 0.0209. Both values are below 0.05, so this is a material inferential shift but **not** a significance-threshold crossing.

## Structural revision pilot

On the separate ten-event authored dependency-graph pilot, flat binary propagation preserved precision but missed conjunctive dependency failures, whereas unconditional downstream reachability achieved complete impact recall by over-invalidating objects that retained an alternative sufficient support path. Support-set provenance and full transactional revision produced the same impact sets on these controlled cases. This result isolates the logical contribution of AND/OR support semantics from transaction semantics: impact-identification gains should be attributed to support representation, not to the transaction layer.

## Transaction fault injection

We therefore evaluated the revision transaction separately. Six deterministic checks passed. A normal two-entity revision committed; an injected second-entity write failure restored exact pre-image hashes and recorded `rolled_back`; a simulated crash in the `applying` phase was recovered from the journal; removing one of two alternative sufficient support paths left the claim supported; an 11-file revision was faulted at every entity-write position and restored all pre-images in 11/11 trials; and two independent revision CLI processes launched concurrently both committed while leaving both evidence/claim pairs in the expected final states. These checks support the implemented local atomicity/recovery protocol under the tested fault model; they do not imply distributed-database durability.

## Uncertainty

Repository-clustered bootstrap intervals are provided only as a descriptive sensitivity analysis over the ten-event authored structural pilot. Because those dependency graphs and gold impact sets were authored for mechanism development, the intervals do not constitute external-validation uncertainty. Confirmatory inference is reserved for independently annotated events collected under `PREREGISTRATION.md`.

## Claims that should not yet appear in the abstract

Do not state that ResearchLedger has been externally validated on real research trajectories, that real agents register dependencies accurately, that the 13/13 semantic replay estimates population accuracy, or that transaction semantics outperform support-set provenance on impact identification. Those claims require the confirmatory study with full executable trajectories and independent annotation.
