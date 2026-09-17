---
type: research-project
topic: A minimal, checked example ResearchLedger workspace
initial_topic: A minimal, checked example ResearchLedger workspace
domain: tooling
created_at: "2026-09-01T09:00:00Z"
updated_at: "2026-09-01T09:20:00Z"
---

# Research Project

## Research Statement
This is a tiny, shipped example workspace — not a real research project. It exists so a new user
(or CI) can run `researchledger validate --strict` against something real and see it pass clean,
and so `researchledger trace C001` has something to walk. See
[`../../reference/run-ledger.md`](../../reference/run-ledger.md) for what each file means.

## Motivation
Demonstrate the full chain paper statement -> claim -> evidence -> run -> metrics -> artifact,
end to end, with every link actually checkable.

## Research Questions
- Does the baseline classifier exceed 90% accuracy on the held-out split?

## Scope
In scope: one claim, one evidence record, one run. Out of scope: everything else — this is a
quickstart fixture, not a template for a real project's size.

## Domain
Tooling / example.
