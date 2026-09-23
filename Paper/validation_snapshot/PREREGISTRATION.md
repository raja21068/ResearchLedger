# Pre-registration for the external revision-integrity validation

## Study objective

Evaluate whether transactional support-set revision protects previously generated scientific state after genuine upstream scientific-software revisions, while avoiding unnecessary invalidation of objects that retain a complete support path.

This document deliberately separates the **current 10-event authored pilot** from the future confirmatory study. Pilot cases, pilot mappings, and pilot effect sizes must not be counted as confirmatory observations.

## Confirmatory sample

- Target: **at least 60 revision events from at least 15 repositories**.
- Preferred target: 100–150 events from 25+ repositories if acquisition cost permits.
- Unit of clustering: repository.
- Inclusion requires a pinned before/after commit pair, an executable scientific task, and a revision with a plausible effect on numerical output, statistical inference, data composition, model behavior, or scientific defaults.
- Exclude documentation-only changes and changes for which neither version can be executed or reconstructed sufficiently to determine output semantics.
- A repository may contribute multiple events, but uncertainty is estimated by repository-clustered resampling.

## Blinding and gold construction

Two annotators independently receive the before/after code or diff, executable outputs, task definition, and object descriptions. They do **not** receive TRL registrations, system predictions, or the authored pilot graph. Annotators label affected claims, decisions, and assertions and identify conjunctive versus alternative support. A third annotator adjudicates disagreements. Agreement is reported before adjudication.

## Systems

1. No revision-state management.
2. Full rebuild / invalidate-all control.
3. Downstream reachability provenance.
4. Flat binary dependency propagation.
5. AND/OR support-set provenance without transaction semantics.
6. Full ResearchLedger transactional support-set revision.

Where feasible, add an ATMS/positive-Boolean-provenance implementation as a strong formal comparator rather than treating flat binary edges as the only logical baseline.

## Primary outcomes

1. **Stale-assertion escape rate** = affected assertions left admissible / all truly affected assertions.
2. **False invalidation rate** = unaffected objects invalidated / all unaffected objects exposed to the revision.

Primary contrasts are full ResearchLedger vs flat binary edges for stale escape, and full ResearchLedger vs downstream reachability/full rebuild for false invalidation.

## Secondary outcomes

- claim impact recall and precision;
- exact event impact-set match;
- selective recomputation precision;
- number of tool executions avoided relative to full rebuild;
- recovery correctness after recomputation;
- time-to-safe-state;
- dependency precision/recall;
- support-set coverage;
- annotation agreement and adjudication rate.

## Statistical analysis

Report point estimates with 95% repository-clustered bootstrap confidence intervals. Resample repositories with replacement and carry all events from a sampled repository into a bootstrap replicate. Use paired differences because all systems are evaluated on the same events. The confirmatory analysis uses a fixed random seed and at least 10,000 bootstrap replicates. Do not treat individual events from the same repository as independent observations.

## Failure analysis

Every false negative and false positive is assigned, after the primary analysis, to one of: missing dependency registration, wrong support-set structure, assertion-binding error, unsupported claim-to-claim dependency, ambiguous scientific interpretation, execution mismatch, or other. This analysis is descriptive and cannot redefine the primary gold labels.

## Stopping and reporting

The minimum sample target is repository-based, not performance-based. Do not stop collection because the preferred method reaches a desired accuracy. Report all included events and all exclusions with reasons. Report the authored 10-event pilot separately as development evidence only.
