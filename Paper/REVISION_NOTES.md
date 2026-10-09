# AutoResearch-Ledger manuscript revision notes

This revision strengthens the manuscript at the construct, novelty, mechanism, and evidence-hierarchy levels without adding unexecuted results or changing reported numerical outcomes.

## Main manuscript changes

1. **Reframed the central claim** around a transactional state-control layer for *declared* research dependencies. The abstract now makes the registered-graph conditionality explicit before presenting results.
2. **Separated the two technical contributions**: AND/OR support semantics determine selective impact identification; the transaction layer contributes atomicity, rollback, predecessor freshness, recovery, concurrency protection, and auditable history.
3. **Added an operational construct table** distinguishing what TRL can compute from what still requires scientific judgement. It covers evidence records, sufficient sets, required premises, non-epistemic dependencies, lineage, assertion binding, and ledger-live/ledger-admissible states.
4. **Reduced epistemic over-reading** by defining `live` and `admissible` as graph-relative workflow labels rather than truth, credibility, or scientific-validity judgements.
5. **Strengthened the construct-validity argument**. The adjudicated reference graph is no longer rhetorically treated as self-evident ground truth: independent annotator agreement is explicitly a gate before system accuracy.
6. **Sharpened the novelty boundary** relative to ATMS, positive-Boolean provenance, workflow provenance, dependency invalidation, optimistic concurrency, and predecessor-anchored activation. The manuscript now makes only a composition-level novelty claim.
7. **Clarified the evidence hierarchy** into formal/implementation conformance, transactional integrity, bridge/ecological plausibility, construct validity, end-to-end agent validity, and human auditability.
8. **Reframed synthetic results** as specification/mechanism evidence rather than estimates of real-world research accuracy.
9. **Expanded limitations** around construct assignment, binary evidentiary support, statistical dependence, claim edits, assertion-binding acquisition, distributed durability, and native-system comparison.
10. **Rewrote the discussion and conclusion** to state exactly what is demonstrated now and what remains publication-critical.

## Substantive consistency fix

The previous manuscript used two claim-state vocabularies without explaining the distinction. The core TRL specification uses `unsupported/supported/verified/contested/stale`, whereas the ResearchLedger v2.2 bridge used in the tracked historical proxy uses `hypothesis/provisional/supported/mixed/contradicted/withdrawn`. The reported `supported -> hypothesis -> supported` lifecycle is now explicitly identified as a **ResearchLedger-native bridge lifecycle**, not a transition in the core TRL state table. The supplement documents the semantic correspondence.

## Supplement changes

- Added an explicit representation-semantics vs construct-acquisition boundary.
- Clarified interpretation of the zero-tier synthetic-fixture verification policy.
- Added the bridge-status vocabulary explanation.
- Replaced the compact annotation paragraph with a preregistered counterfactual relation codebook including positive criteria and non-examples.
- Narrowed the truth-maintenance comparison to the classical JTMS/ATMS formalisms actually cited.
- Strengthened the interpretation boundary between construct validity and end-to-end agent validity.

## What was deliberately not changed

No human annotation result, Paper2Agent old/new result, population-level accuracy claim, or additional empirical result was invented. The decisive external-validation study remains unexecuted and is still identified as necessary for a broad high-level journal claim.

## Build verification

- Revised main manuscript compiles successfully with `latexmk`/`biber`: 12 pages.
- Revised supplement compiles successfully: 10 pages.
- No undefined references or citations were found in the main manuscript build.
- PDFs were rendered and visually inspected after compilation.
