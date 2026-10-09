# System integration contract

## Responsibility separation

- Paper Factory is the controller. Its checkpoint is a performance optimization, not a proof of a valid experiment.
- ResearchLedger owns the persistent claim, evidence and run graph.
- The adapter `factory.integrations.ledger` owns cross-system mapping and runs *after* the isolated experiment completes.
- `researchledger.runner.record_external_execution` takes already-validated external outputs, snapshots metrics/artifacts, writes an environment record, and seals a run with the normal ResearchLedger chain-locking logic. It **never** launches untrusted experiment code.
- `researchledger.reproduce` explicitly rejects imported runs to prevent accidental bare-host execution.

## Key data invariants

1. S1 chooses a falsifiable idea before `C###` is allocated. New idea contents allocate a different claim instead of rewriting history.
2. S4 must complete a verified code-and-result-slot contract and a successful Docker run attempt; invalid or incomplete results are rejected.
3. Source results are hashed, copied into `R####/metrics.json`, and marked as external, pilot, not independently reproduced. Additional S4 outputs are snapshotted as hashed run artifacts.
4. `E###` has `status=checked`, not `verified`, and may link to the selected current C###. Claim status is computed by ResearchLedger; checked evidence can only make it provisional.
5. `control/ledger_s4_receipt.json` binds the S4 code/output to a specific run and evidence record. S5 blocks if the receipt fails integrity, if datasets/source repo/results spec changed or if the ResearchLedger graph reports errors.
6. The pipeline checkpoint tracks ledger receipts alongside stage outputs; a deleted/altered receipt invalidates resume of S4 and downstream stages.
7. `researchctl audit` includes ledger status but always sets `publication_ready: false`.

## Failure and recovery

An interruption between sealing the immutable R#### and writing its receipt can leave an *orphaned* but valid historical run. Do not delete that run. Re-running S4 generates an additional historical run and receipt. This is the safe fail-closed choice rather than rewriting an immutable record.

If evidence is legitimately revised through the standalone ledger's revision workflow, rerun the ledger audit. A receipt tied to the original evidence SHA may need an explicit documented reconciliation; no change to verified status is silently trusted.

Adding `ledger_enabled: true` to an old workspace intentionally invalidates checkpoints because the stage context changes. S1 and S4 must be re-run to create truthful records. Back up prior outputs first.

## Not implemented by this integration

- Independent correctness proof for generated algorithms.
- Automatic PubMed/OpenAlex/arXiv literature verification from downloaded sources.
- Four actual concurrent reviewers or a new autonomous multi-agent controller.
- Independent statistical reproduction of imported container results.
- Submission-ready manuscripts or venue-specific acceptance scoring guarantees.

Those remain research and engineering tasks; skills are methodology documents, not evidence that they were executed.
