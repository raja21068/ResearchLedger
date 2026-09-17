# Run Ledger v2: `researchledger` CLI, typed entities, validation, tracing

This is the v2 hardening of ResearchLedger's provenance layer: a standalone Python package
(`researchledger/`, `pip install -e .` from the plugin root) that turns
**paper statement → claim → evidence → run → metrics → raw artifact** from a documented convention
into a mechanically checked one. It is a companion tool to the skills, not a skill itself — Claude
invokes it via `Bash researchledger <command>` when a skill needs to record, validate, migrate, or
trace something; a human can run it directly from a terminal, and `researchledger validate
--strict` is built to run in CI (see `.github/workflows/ci.yml`).

Selectively adapted from [AutoResearch](https://github.com/raja21068/AutoResearch)'s engineering
(execution capture, environment recording, resource controls, metric collection) — deliberately
**without** importing its multi-agent orchestrator, planner, or paper-writer, which overlap with
what the skills already do as plain-file conventions and would undermine the "no server, no
daemon" design this plugin is built around.

## The one rule everything else serves

> Every quantitative claim in a manuscript should be traceable, through a fixed chain, to the
> exact run and artifact that produced it — and every link in that chain should be independently
> checkable, not merely asserted.

Concretely: `paper.md` statement → `C<NNN>` claim → `E<NNN>` evidence → `R<NNNN>` run →
`metrics.json` → a hashed artifact. `researchledger trace` walks this chain in both directions;
`researchledger validate` checks every link mechanically; `researchledger validate-paper` checks
that the manuscript actually uses the chain, not just that the chain is internally consistent.

**Try it now**: [`examples/quickstart/`](../examples/quickstart/) is a small, real workspace shipped
in this repo — `cd examples/quickstart && researchledger validate --strict` passes clean, 100% on
every metric, out of the box. See its own `README.md` for what it demonstrates.

This is also wired into four of the skills, not just documented for them to find on their own:
`research` (bootstraps the ledger, surfaces `researchledger report` in status), `experiment-design`
(routes execution to `researchledger run`), `reproducible-implementation-spec` (specifies runs in
terms of `researchledger run`/`--seed`/`--data`, verifies via `researchledger reproduce`), and
`evidence-assessment` (audits via `researchledger trace`/`validate`, creates evidence via
`researchledger evidence create`).

## Workspace additions

```text
.researchledger/index.json       # cached graph summary — see "The cached index" below
research/runs/R<NNNN>/           # immutable execution records
├── manifest.json                  # the run's full record — see schema below
├── environment.json               # python version, platform, installed packages
├── command.txt                    # the exact command line, shell-quoted
├── stdout.log / stderr.log
├── metrics.json                    # optional — copied via --metrics, or written directly by
│                                     #   the command into $RESEARCHLEDGER_RUN_DIR
└── artifacts/                      # anything the command writes into
                                     #   $RESEARCHLEDGER_ARTIFACTS_DIR, hashed on completion
migration-report.json            # only after `researchledger migrate` (not a dry run)
backup/v1-<timestamp>-<hex>/     # only after `researchledger migrate` — pre-migration snapshot
```

Run ids are `R<NNNN>` — 4-digit zero-padded, next id = highest existing + 1, allocated under a
workspace-wide advisory lock (`researchledger/workspace.py:ledger_lock`) so two concurrent
`researchledger run` processes can never collide on the same id — see "Concurrency" under Tamper-
evident run chain below for why *sealing* (not just allocation) also needs that same lock. **A run
directory is written once and never hand-edited** — every write to
`manifest.json`/`environment.json`/`metrics.json` goes through `atomic_write_json` (write to a
sibling temp file, fsync, `os.replace`), so a crash mid-write leaves the previous file intact
rather than a half-written one. If a result needs correcting, run it again and supersede the
evidence that cited the old run.

## Typed entities and schema validation

Evidence, claims and decisions are validated against JSON Schemas (`schemas/evidence.schema.json`,
`claim.schema.json`, `decision.schema.json`, `run.schema.json`) using the `jsonschema` package —
not a hand-rolled validator. A v1-style file (comma-delimited strings, no `schema_version`) is
schema-invalid under v2 (`RL003`) until migrated; see "Migrating from v1" below. Every entity now
carries `schema_version: "2.0"`.

## Status vocabulary

Evidence and claims use **different, deliberately non-overlapping** vocabularies — the whole point
is that a claim can never accidentally inherit the word "verified" from a single experiment.

**Evidence**: `proposed → observed → checked → verified`, or `contradicted` / `invalidated` /
`superseded` from any state. A run completing successfully earns `checked` — never `verified`;
promoting to `verified` (independent corroboration: a second run, a second reviewer, a cross-check
against an external source) is a separate, deliberate call. `researchledger evidence create`
enforces this at the API level: it refuses `--status verified` when creating evidence `--from-run`.

**Claims**: `hypothesis → provisional → supported`, or `mixed` / `contradicted` / `withdrawn`.
`withdrawn` is manual-only — a human or agent decision to retire a claim — and is never produced or
overridden by recomputation.

**Recomputing a claim's status from its evidence is deterministic code, not judgment**
(`researchledger.models.recompute_claim_status`, ignoring superseded evidence):

| Live evidence state | Result |
|---|---|
| contradicting at `checked`/`verified` **and** supporting at `observed`/`checked`/`verified` | `mixed` |
| contradicting at `checked`/`verified`, no qualifying support | `contradicted` |
| supporting at `verified` | `supported` |
| supporting at `observed`/`checked` only | `provisional` |
| none of the above | `hypothesis` |
| claim already `withdrawn` | `withdrawn` (unchanged) |

`researchledger evidence create` calls this the moment it links evidence to a claim, so a claim's
recorded status is usually already correct by construction. `researchledger validate` re-checks it
anyway (`RL310`, status drift) as the backstop for hand-edited files — a warning by default,
promoted to a hard failure under `--strict`.

## CLI reference

Install once per machine from the plugin root: `pip install -e .` (pulls in PyYAML and jsonschema
only).

| Command | What it does |
|---|---|
| `researchledger init [path]` | Create `research/{evidence,claims,decisions,runs}/` and `.researchledger/` if missing, at `path` or the current directory. Idempotent. |
| `researchledger run [options] -- <command>` | Execute `<command>` as a new immutable run. See options below. |
| `researchledger validate [--strict] [--json]` | Run the deterministic RL-coded validator (next section). `--strict` promotes a fixed set of warnings to errors and exits non-zero on any error — safe to wire into CI. |
| `researchledger report [--json]` | The same integrity summary as `validate`, but never gates (always exits 0) — for a status dashboard, not a CI check. |
| `researchledger trace <C###\|E###\|R####>` | Forward from a claim/evidence id (paper → claim → evidence → run → metrics → artifact → hash), or reverse from a run id (which evidence/claims/manuscript sections depend on it). |
| `researchledger inspect <R####>` | Print a run's `manifest.json` verbatim. |
| `researchledger reproduce <R####> [--tolerance F] [--repeat N] [--z-score Z] [--no-isolate] [--keep-worktree]` | Re-execute a run's exact command, isolated in a fresh git worktree at its original commit when possible, and report whether metrics/artifacts match — within a fixed tolerance (default), or against the distribution of `N` repeated reproductions when the metric has real run-to-run noise. |
| `researchledger index` | Force-rebuild `.researchledger/index.json`. Also runs automatically at the end of `run`, `validate`, `migrate`, `evidence create`, and `reproduce`. |
| `researchledger migrate --from v1 [--dry-run]` | Rewrite v1 evidence/claims/decisions into the v2 schema. Backs up first; see "Migrating from v1". |
| `researchledger evidence create [--from-run R####] [--supports C###]... [--contradicts C###]... [--source-kind K] [--status S] [--name N]` | Create a graph-consistent evidence record: correct id, `schema_version`, bidirectional claim edges, recomputed claim status — all in one step. |
| `researchledger validate-paper <path> [--json]` | Audit a manuscript's quantitative assertions against the claim/evidence/run graph — see "Manuscript provenance" below. |

`run` options: `--seed <int>` (recorded, not enforced — the command itself must actually seed its
own RNGs), `--claim <id>` (repeatable), `--plan <id>`, `--metrics <path>` (a JSON file the command
produced, copied in as `metrics.json`), `--timeout <seconds>`, `--retries <n>` (re-run on non-zero
exit; every attempt's exit code is kept, only the final attempt's logs are), `--env <NAME>`
(repeatable — allowlist that one environment variable's *value* into the manifest; nothing is ever
captured that isn't explicitly named here), `--data <path>` (repeatable — a file or directory
input dataset to content-hash into the manifest's `inputs`; validated to exist *before* a run id is
allocated, so a typo doesn't burn a run number).

Inside the command, three environment variables are set: `RESEARCHLEDGER_RUN_ID`,
`RESEARCHLEDGER_RUN_DIR`, `RESEARCHLEDGER_ARTIFACTS_DIR` — write result files into the artifacts
directory (or a `metrics.json` straight into the run directory) and the run picks them up
automatically.

## The run manifest (`manifest.json`, schema `schemas/run.schema.json`)

```json
{
  "schema_version": "2.0",
  "run_id": "R0001",
  "status": "completed",
  "started_at": "2026-09-16T09:14:22Z",
  "finished_at": "2026-09-16T09:29:41Z",
  "command": "python train.py --config configs/base.yaml",
  "command_argv": ["python", "train.py", "--config", "configs/base.yaml"],
  "working_directory": ".",
  "git": { "commit": "8da09bc...", "dirty": false },
  "randomness": { "seed": 42 },
  "targets": { "claims": ["C001"], "plan": "P003" },
  "environment": "environment.json",
  "environment_digest": "sha256:...",
  "hardware": {
    "cpu": "...", "cpu_count": 16, "total_memory_bytes": 34359738368,
    "gpus": [], "gpu_driver_version": null, "cuda_version": null
  },
  "env_vars": {},
  "metrics": "metrics.json",
  "inputs": [{ "path": "data/imagenet-c", "sha256": "a1b2..." }],
  "artifacts": [{ "path": "artifacts/results.csv", "sha256": "9f02..." }],
  "timeout": null,
  "attempts": [{ "attempt": 1, "exit_code": 0, "timed_out": false }],
  "exit_code": 0,
  "previous_run_hash": "sha256:7c3e..."
}
```

`status` is `completed` (exit 0), `failed` (non-zero exit, no timeout), or `timeout`. `git.commit`
is `null` outside a git repository. **The manifest is written entirely by `researchledger run`'s
own code — an LLM never writes or edits it.** That's the actual guarantee behind "don't let an LLM
fabricate this": a skill can ask Claude to run `researchledger run -- ...` and read the result back,
but the numbers in the manifest came from the subprocess's actual exit code, wall-clock time, git
state and file hashes, not from anything Claude generated.

`inputs` mirrors `artifacts` but for data the run *consumed* rather than produced — populated by
`--data`, hashed with `researchledger.hashing.sha256_path` (a directory's hash covers every file's
relative path and content, order-independent, so it detects an added/removed/changed file the same
as a changed one). `researchledger validate` checks these exist and still match (`RL212`/`RL213`),
exactly like artifacts.

## Tamper-evident run chain

Artifact hashes catch a changed *result*; nothing so far catches a rewritten *history* — hand-edit
an old run's `manifest.json` (say, to quietly flip a failed run to `exit_code: 0`) and nothing
would notice. `previous_run_hash` closes that gap: every run's manifest records the SHA-256 of the
immediately preceding run's manifest.json — the first run in a workspace records `null`.
`researchledger validate` doesn't assume the chain matches numeric run-id order; it follows each
run's actual `previous_run_hash` pointer to whichever run's *current* manifest hash it names. If a
pointer doesn't match any existing manifest, or two runs both claim the same predecessor (a
branch), or more than one run claims to be the root, that's `RL220` — history may have been
altered, or duplicated. Runs recorded before this field existed are `RL221` ("legacy, unchained") —
a warning, not an error.

This is the same idea as a git commit chain or a lightweight blockchain, applied to run manifests
specifically. It costs nothing extra to produce (`researchledger run` already writes the manifest
once and never again) and nothing extra to check (one hash per run, already being read for other
checks).

**Concurrency.** Id allocation and command *execution* are two different things, and only the
first needs to be serialized — `researchledger run` grabs the next run id under a single
workspace-wide lock (`ledger_lock`, held for a few filesystem operations) and releases it
immediately, so concurrent `run` invocations execute their commands fully in parallel. What can't
happen in parallel is *sealing*: assigning `previous_run_hash` and writing `manifest.json`. A
run's seal reacquires `ledger_lock` right before that write, reads a small `.chain-tip` file (the
hash of whichever run sealed most recently), writes its own manifest referencing it, then updates
the tip — all inside the same lock acquisition. This is a real fix for a real, confirmed bug: an
earlier version computed the "previous" hash by scanning for the highest-numbered *existing* run
right after allocating an id, before execution — under concurrent `run` invocations, several runs
would all see the same (not-yet-sealed) predecessor, or none, and `validate` would report the
resulting chain as tampered even though nothing had actually been altered. 8 concurrent runs
produced 12.5% chain integrity before the fix; the same test now reports 100%
(`tests/test_runner.py::test_concurrent_runs_produce_a_valid_chain`).

`researchledger evidence create` uses the same `ledger_lock` around its entire critical section —
claim-existence check, id allocation, and every write — for the same reason: an earlier version
called `next_id()` with no lock at all, and 8 concurrent `evidence create` calls could hand out the
same id to two callers, with the second write silently clobbering the first
(`tests/test_evidence.py::test_concurrent_evidence_creates_never_collide_on_id`).

## The validator's rule catalog

Every finding carries a stable code (`researchledger/codes.py`), documented here so a validator
message is greppable, not free text:

| Code | Severity | Meaning |
|---|---|---|
| `RL001` | error | Malformed id (wrong prefix/width). |
| `RL003` | error | Frontmatter/manifest fails JSON Schema validation (covers status-vocabulary validity too, and run manifests, not just evidence/claims/decisions). |
| `RL004` | error | A run's `manifest.json` exists but could not be parsed at all — corrupted ledger state is reported, never silently dropped from the run count. |
| `RL101` | error | A cross-reference (`supports`, `evidence`, `supersedes`, a provenance marker, ...) points at an id that doesn't exist. |
| `RL102` | warning | A cross-reference isn't mirrored on both sides (e.g. `Evidence.supports` lists a claim that doesn't list the evidence back). |
| `RL110` | error | A claim past `hypothesis` cites zero evidence. |
| `RL111` | error | Experiment/computation evidence past `proposed` cites zero runs. |
| `RL112` | warning | Evidence cites a run that produced neither `metrics.json` nor artifacts. |
| `RL120` | error | A claim's only live supporting evidence is `contradicted`/`invalidated`. |
| `RL201` | error | A manifest-listed artifact is missing on disk. |
| `RL202` | error | An artifact's content no longer matches its recorded SHA-256 — tampering or bit rot. |
| `RL210` | warning | A run has no recorded `environment.json` reference. |
| `RL211` | error | Evidence cites a run whose `exit_code` was non-zero. |
| `RL212` | error | A manifest-listed input dataset is missing on disk. |
| `RL213` | error | An input dataset's content no longer matches its recorded hash. |
| `RL220` | error | A run's `previous_run_hash` doesn't match the prior run's actual manifest — history may have been altered. |
| `RL221` | warning | Run predates the tamper-evident chain (no `previous_run_hash` recorded). |
| `RL301` | warning | `supersedes`/`superseded_by` isn't symmetric, or the superseded record's status wasn't updated. |
| `RL302` | warning\* | A claim depends on superseded evidence. |
| `RL303` | warning | Run-backed evidence has no reproduction note in its body. |
| `RL310` | warning\* | The claim's recorded status disagrees with what `recompute_claim_status` derives from its evidence. |
| `RL401` | error | A manuscript provenance marker (`<!-- rl:claim=... -->`) references a nonexistent claim/evidence id. |

\* `RL302` and `RL310` are in `codes.STRICT_ESCALATES`: `validate --strict` treats them as
build-failing errors; plain `validate`/`report` report them as warnings only. Every other
warning-level code never gates the build, even under `--strict` — they flag things worth a human's
attention (a missing repro note, an unmirrored edge under active editing) rather than broken
invariants.

These also encode the graph-shape constraints from the formal model — claims need evidence once
they're not bare hypotheses (`RL110`), experimental evidence needs a run once it's not just
proposed (`RL111`), and a run evidence relies on has to have actually succeeded (`RL211`).

## Fail-open vs. fail-closed

This is a deliberate split, not an inconsistency:

- **The context hook** (`hooks/inject_research_context.py`) fails open: any exception, or any
  workspace it doesn't recognize, and it prints nothing and exits 0. It must never turn into a
  visible failure on every single prompt.
- **Everything else** — `validate`, `run`, `migrate`, `reproduce` — fails closed: real exceptions
  propagate, exit codes are meaningful (`0` success, `1` a real failure, `2` a usage error), and
  `validate`/`report` always emit a structured report even when things are broken. A validator that
  silently swallows an error and prints "everything appears consistent" would be worse than useless.

## Provenance tracing, both directions

`researchledger trace C014` walks forward: which paper sections reference `C014` (by a provenance
marker or the bare id token, per `papers.md`'s convention) → the claim's statement → each
supporting evidence record and its status → each run it cites, with seed, a few metric values,
`metrics.json`'s presence, and an aggregate artifact-hash-verification count.

`researchledger trace R0042` walks in **reverse**: every evidence record that cites this run, every
claim that evidence supports, and every manuscript section that claim is used in — "what depends on
this run" is exactly as answerable as "what does this claim depend on."

## Executable reproducibility

`researchledger reproduce R0042` does not just print a stored command string:

1. Loads the run's manifest: `command_argv`, `seed`, `targets`, and the original `git.commit`.
2. If the workspace is a git repository and the run recorded a commit, checks out that exact
   commit into a **fresh, isolated `git worktree`** in a temp directory (never touching the current
   working tree) and re-runs the command there. If either condition fails, it re-runs in place and
   says so plainly — isolation is never silently downgraded.
3. Compares the new run's `metrics.json` against the original, numeric key by numeric key, within
   `--tolerance` (default `1e-3`), and compares every original artifact's hash against the new
   run's artifact of the same relative path.
4. Reports `REPRODUCED ✓` only if the new run's exit code was 0 **and** every metric matched within
   tolerance **and** every artifact hash matched.

```text
Reproduction R0042 -> R0051

Isolation: isolated git worktree at commit 8da09bc12345

Original metric:
  accuracy = 0.9137

Reproduced:
  accuracy = 0.9134 ✓

Tolerance: ±0.001

Result: REPRODUCED ✓

Artifacts: 7/7 verified
```

Isolation only protects you if the command's own paths are relative to its working directory —
`researchledger run -- python train.py` (relying on `cwd`) reproduces the worktree's checked-out
code; a command hard-coding an absolute path back into the main tree does not, and there is no way
for the runner to detect that from the outside. This is a real, documented limitation, not a silent
gap.

**`--repeat N`** replaces the single-point tolerance check with a distribution check: the same
isolated worktree is reused for all `N` re-executions (checked out once, not `N` times), each
metric's reproduced values are collected, and the comparison becomes `|original - mean| <=
max(tolerance, z_score * stddev)` (`--z-score`, default `2.0`) instead of `|original - reproduced|
<= tolerance`. `repeat=1` degenerates to exactly the old single-value check (`stddev` is `0`, so
`max(tolerance, 0) == tolerance`) — this isn't a separate code path, it's the same formula with one
sample. Use it for anything with real run-to-run noise (non-deterministic GPU kernels, sampling);
a fixed epsilon is the wrong tool for "is this within the noise we'd expect anyway."

## Manuscript provenance

A manuscript statement can carry an invisible provenance marker right after it:

```markdown
Our method improved F1 by 4.8 percentage points.
<!-- rl:claim=C014 -->
```

(A longer form, `<!-- rl: claim=C014 evidence=E031,E034 -->`, is also accepted for explicitness,
but the claim id alone is enough — the evidence is already reachable from the claim.)

`researchledger validate` checks every marker's ids actually exist (`RL401`).
`researchledger validate-paper paper.md` goes further — it scans every non-heading, non-table
line for a sentence containing a digit, and reports:

```text
Manuscript provenance audit

Quantitative assertions found:      31
Linked to claim records:            30
Backed by verified evidence:        27
Backed by reproducible runs:        24
Unsupported:                         1
Stale/superseded evidence used:      2
```

"Backed by reproducible runs" means the linked claim's evidence cites a run that both exited 0 and
recorded a git commit — the same bar `reproduce` checks, applied here without actually re-running
anything.

## Migrating from v1

```bash
researchledger migrate --from v1 --dry-run   # report only, writes nothing
researchledger migrate --from v1             # backs up, then rewrites
```

For each evidence/claim/decision file not already on `schema_version: "2.0"`: backs up the whole
`research/{evidence,claims,decisions}/` tree to `backup/v1-<timestamp>-<hex>/` first (skipped on
`--dry-run`), rewrites comma/pipe-delimited fields into real YAML arrays, renames evidence status
(`unverified→observed`, `supported→checked`, `verified→verified`, `rejected→invalidated`,
`superseded→superseded`), and **recomputes claim status from the already-migrated evidence**
(`recompute_claim_status`) rather than blindly renaming it — a rename alone can't tell "supported"
from "mixed" without looking at the evidence graph. A v1 `superseded` claim seeds as `withdrawn`
(nobody is maintaining it) before recomputation, which respects that seed and leaves it alone. A
file that fails to parse (bad encoding, broken YAML) is recorded under `malformed` with a reason
and left untouched — one broken file never aborts the batch. Writes `migration-report.json` at the
workspace root.

## The cached index

`.researchledger/index.json` is a small, precomputed summary of the graph — counts, per-status
breakdowns, the current integrity metrics, and the top few open validator issues — rebuilt by
`researchledger index` and automatically refreshed by `run`, `validate`, `migrate`,
`evidence create`, and `reproduce`. The `UserPromptSubmit` hook
(`hooks/inject_research_context.py`) reads only this one small file, so its per-turn cost stays
flat regardless of how many evidence/claim/run files exist — it does not re-scan or re-parse the
whole workspace on every prompt. If no index exists yet (a workspace that's never run the CLI), the
hook falls back to a light, dependency-free directory scan instead of failing.

The hook reports **state**, not a prescribed stage — a fixed "current stage" table would conflict
with this plugin's own "no fixed pipeline" design (see `README.md`). It prints claim/evidence
counts by status, run counts, the current error/warning count, and (from the index's cached
`top_issues`) one recommended unresolved issue — deciding what to do about it stays with the skills
and the human, not the hook.

## What this does not do

It does not run anything unattended, decide what to run next, retry a failed experiment with
different hyperparameters, or judge whether a result is "good enough" — `researchledger run`
executes exactly the command given to it, `--retries` bare-repeats the identical command, and
`reproduce` re-executes and compares, nothing more. Planning what to run and deciding whether
evidence is sufficient stays with the skills (`experiment-design`, `evidence-assessment`,
`go-no-go-decision`) and the human in the loop — see point 18 of the v2 design discussion: LLM
judgment and deterministic code stay on their own sides of that line on purpose.

## Quality gates, as actually run in this repo

- **Tests**: `python -m pytest tests/ --cov=researchledger` — 168 tests, 97% statement coverage on
  `researchledger/` (above the ≥95% target; the remaining ~3% is a handful of defensive `except`
  branches and the `if __name__ == "__main__":` entry-point guard — see the test suite for exactly
  what's covered, module by module).
- **Lint**: `python -m ruff check researchledger/ tests/` — clean.
- **Types**: `python -m mypy researchledger/` — clean.
- **Dependencies**: `pip-audit` against this package's only two runtime dependencies (`PyYAML`,
  `jsonschema`) — zero known vulnerabilities at time of writing.
- **A real example, not just tests**: [`examples/quickstart/`](../examples/quickstart/) is a
  shipped, real workspace that `validate --strict` and `validate-paper` both pass clean —
  `tests/test_examples.py` re-checks this on every test run, so a future validator change that
  breaks it fails CI, not just a user's real workspace.
- **CI**: `.github/workflows/ci.yml` runs the above on Ubuntu, Windows and macOS across Python
  3.9–3.12, plus a CLI smoke test (`init` → `run` → `validate --strict` → `report`) and the shipped
  example's own `validate --strict`/`validate-paper` — this repo's own session only actually
  executed the Windows leg locally; the matrix is what CI verifies on push.
