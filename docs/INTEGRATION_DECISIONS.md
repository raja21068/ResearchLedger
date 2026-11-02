# Integration decisions: the Claude Code implementation plan, checked against the code

Date: 3 November 2026. Input: `ResearchLedger_Claude_Code_Implementation_Plan.md` (user-supplied). Method: each requirement
was compared with the actual `feature/web-app-paper-studio` code; the plan was used as a checklist, not as a script.
Where this document and the plan differ, this document records why.

Context the plan did not have: the plan targets `factory/` and the `researchledger` CLI. Most of the work since has been
in the web application (`webapi/`, `frontend/`), which already contains the single project database, the single run
ledger bridge and the single approval system the plan insists on. No code from Agentic Scientist, AutoResearchClaw or
AI Scientist v2 has been copied; only ideas were used, and nothing from them was imported. (AI Scientist v2's licence
is custom, which is a further reason to keep it that way.)

## Requirement by requirement

| Plan item | State in the code | Decision |
|---|---|---|
| **P0 contracts**: task contract, structured receipt | server runs have receipts with fingerprints; **agent tasks had none** | **Build:** a server-written receipt for every agent task (identity, parent, operation, permitted workspace, artifacts with hashes, status, timing). The agent cannot forge it because the server creates it |
| **P0 isolation**: per-task worktrees, conflict detection, Codex | one agent task per project at a time (no conflicts possible); no Codex adapter | **Defer.** Isolation matters once two agents run in parallel, which needs a Codex adapter first. Today's rule is safe. Revisit after the trial |
| **P0 canonical ledger written only by the controller** | the ledger is written only by `ledger_bridge.py`; agents have no ledger access | **Already true.** Add adversarial tests that pin it down |
| **P0 memory** (categories, sources, qualified lessons) | built: 5 domains, sources, history, supersession, proposals need approval, verified reviewer findings | **Extend:** lessons from **other projects** are retrieved with provenance, labelled as unverified for this project, and never authoritative. Today a lesson never leaves its project |
| memory: proposed / observed / checked / corroborated lessons | statuses: proposed, active, needs_review, superseded, rejected | **Keep.** An "active" memory records where it came from and whether a human approved it; a separate "corroborated" level would add ceremony without evidence |
| memory: embeddings | none, by design | **Keep none.** SQLite FTS5 plus domain and tag matching; revisit only if retrieval measurably fails |
| **P0 literature**: OpenAlex, Semantic Scholar, arXiv, Crossref, dedup, citation levels | `refcheck.py` verifies a bibliography against Crossref and arXiv; no library, no dedup, search is done by hand | **Build:** a per-project **literature library** with identity (DOI, arXiv id), provenance, duplicate handling, and four separate verification levels. Adapters for OpenAlex, arXiv and Crossref. **Semantic Scholar is left out:** it needs an API key for reliable rate limits |
| citation level "statement is supported" | not checkable by a machine | **Human-only level**, never set automatically; an existing DOI never marks a claim as supported |
| **P1 hypothesis tree** | idea loops keep candidates, rounds and scores; failed ideas are memories | **Leave.** The loop and memory already preserve rejected ideas and reasons; a tree would duplicate them |
| **P1 experiment contracts and output validation** | locked plan, finite-value and slot checks, fresh-results check, receipts | **Already mostly true.** Add **reproducibility levels** so the labels cannot be confused |
| P1 statistical validation profiles | none | **Leave** (domain-specific; needs a concrete need) |
| **P1 review roles** | review loop, Referee Lean, external packet with quote check | **Leave.** More roles without evidence of benefit would only add output |
| **Security tests (adversarial list)** | many guards exist; few are pinned by tests | **Build** the applicable subset as regression tests |
| Docker sandbox | web runs execute on the host after approval | **Unchanged; the decision is the user's** (Docker vs "no sandbox" per run) |
| GUI/dashboard | built | **Out of scope** for this upgrade, as the plan says |

## Why these six

They are the items that either close a defect found in use (lessons never crossing projects; papers re-found in every
search round; agent work without a receipt) or make an existing claim honest (reproducibility labels, tested
security guards). The rest either already exists or needs a prerequisite (Codex) that does not.

## Status (3 November 2026, end of night)

| Step | State |
|---|---|
| 1. Adversarial security tests | Done: `webapi/tests/test_security.py` (path traversal, other project, symlink, zip members, command parsing, forged receipts, failed jobs, concurrent claim ids, no agent write path to the ledger). **It found one real hole:** a receipt file an agent wrote into its workspace was imported as evidence. The ledger import now trusts only runs the server executed (a run row must exist) |
| 2. Agent receipts | Done: `agent_receipts.py`. Written by the server when a task ends, stored outside the workspace, never rewritten, a hash detects hand edits. API `/agent-receipts` |
| 3. Cross-project lessons | Done: a labelled section in `memory/remembered.md`. Only active failure, strategy, experiment and decision memories from other live projects that share words with this project's title or topic; papers and proposed memories never travel |
| 4. Literature library | Done: `literature.py`, the "Paper library" page, the file `literature/library.md`. Duplicates merge on identity only; the `supports` level is human-only |
| 5. Reproducibility levels | Done in `lab.py`: run once, repeated here, repeated elsewhere, not reproduced. Independent replication is never computed |

Not done on purpose: per-task isolation and Codex, hypothesis tree, review roles, statistical profiles, Semantic Scholar.

## Order and gates

1. Adversarial security tests (no behaviour change).
2. Agent receipts.
3. Cross-project lessons.
4. Literature library.
5. Reproducibility levels.

Each step ships with tests, and the full web and ledger suites must be green before the next.

## Open decisions for the user

- Docker for experiment runs, or the host after an explicit "no sandbox" approval (unchanged).
- Whether to build per-task isolation and a Codex adapter after the four-week trial.
- Whether the literature library should also accept a Semantic Scholar API key if one is available.
