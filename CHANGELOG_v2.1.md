# ResearchLedger v2.1 development changelog

- Added AND/OR claim support sets with required-evidence conjunction.
- Added deterministic derived claim-state recomputation after evidence changes.
- Added transactional evidence revision planning/application with optimistic freshness checks, exact pre-image journals, rollback on validation failure, and crash recovery.
- Added `researchledger revision plan` and `researchledger revision apply` CLI commands.
- Extended claim schema/validator coverage for support-set relationships.
- Added a journal-validation study package with thirteen verified historical semantic-revision sources, executable replay fixtures, repository-clustered bootstrap analysis for the ten-event authored structural pilot, ten blind annotation packets, transaction fault injection, and a confirmatory pre-registration.
- Kept the validation boundary explicit: the ten-event authored structural pilot and thirteen-event semantic replay are development evidence and does not substitute for independent real-trajectory annotation.
