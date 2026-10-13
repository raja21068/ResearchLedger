# Idea Discovery V5 — Grounded Discovery, Adversarial Survival, and Empirical Falsification

V5 separates five questions that should never be collapsed into one score:

1. **Is the problem real and still open?**
2. **Can we generate a coherent, useful research direction?**
3. **Does the idea survive prior-work and hostile-review attacks?**
4. **Is the claim actually falsifiable, and can a cheap experiment break it?**
5. **Does real pilot evidence justify spending resources on the full study?**

A literature-surviving idea is **not** automatically empirically verified. V5 therefore introduces `READY_FOR_MVE` as a first-class state. Final `GREENLIGHT` requires executed minimum-viable-experiment evidence.

## Pipeline

```text
Input papers
   ↓
Structured ingestion + source verification
   ↓
Embeddings / clustering / knowledge graph
   ↓
Conflicts + traceable gaps
   ↓
Discovery grounding
   ├─ target 30–50 relevant papers
   ├─ novelty tree (Type 1/2/3/4)
   ├─ challenge → insight tree
   ├─ quote-or-zero evidence checks
   └─ Level 1–4 well-established-solution gate
          Level 1/2 → SWITCH / BLOCK
          Level 3/4 → PROCEED
   ↓
3 research directions
   ↓
Innovator / Pragmatist / Critic evolution × N
   ↓
Track champions
   ↓
════════════ LITERATURE + REVIEWER ADVERSARY ════════════
Phase 10 — weighted scientific scorecard
Phase 11 — destructive novelty search
Phase 12 — closest-work novelty matrix + intellectual-contribution test
Phase 13 — Reviewer #1 top-10 rejection attack
Phase 14 — revise / pivot / kill
   └─ revision restarts Phase 10 with fresh literature search
   ↓
Provisional literature GREENLIGHT
   ↓
════════════ V5 FALSIFICATION ZONE ════════════
Phase 15 — falsifiable hypothesis contract
Phase 16 — Occam + counterexample attack
Phase 17 — independent blind verifier
Phase 18 — minimum viable experiment protocol
Phase 19 — executed-evidence audit + claim/evidence ledger
   ├─ no evidence → READY_FOR_MVE
   ├─ inconclusive evidence → REVISE_EVIDENCE
   ├─ contradiction / fatal flaw → KILL or scientific revision
   └─ scientific revision → restart Phase 10 before re-entering falsification
   ↓
FINAL GREENLIGHT
   ↓
Final-survivor ELO
   ↓
Full-study research architecture blueprint
   ↓
Cross-run ideation memory
   ↓
Final report + dashboard + SESSION
```

## Hard V5 rules

- An under-grounded problem can fail closed before idea generation.
- Level 1/2 solved problems do not enter evolution by default.
- Every material literature/reviewer revision restarts at Phase 10.
- Every falsification-driven scientific revision also restarts at Phase 10.
- The blind verifier receives the hypothesis contract, falsification plan, and MVE protocol—not the generator's enthusiasm, prior scores, or private rationale.
- V5 never fabricates empirical support. **No executed MVE evidence means no final GREENLIGHT.**
- A negative or inconclusive MVE is useful evidence; the pipeline records it instead of rewriting the claim to appear successful.
- ELO is relative ranking only and runs on final GREENLIGHT ideas.
- Generated MVE commands are never auto-executed by default.

## Quick start

```bash
cp .env.example .env
# add ANTHROPIC_API_KEY

# Put PDF/TXT/MD papers in input_papers/
./run.sh
```

Useful modes:

```bash
./run.sh --checkpoint
./run.sh --resume
./run.sh --skip-embeddings
./run.sh --no-quality
./run.sh --topic "My Topic"
./run.sh --dashboard-only
./run.sh --session-only
python scripts/run_pipeline.py --falsification-only
```

When an idea reaches `READY_FOR_MVE`, inspect its generated protocol under:

`output/falsification/IDEA-xxx/round_yy/phase18_mve_protocol.json`

Run that pilot outside the pipeline, then place the real result in:

`output/mve_evidence/IDEA-xxx.json`

See `output/mve_evidence/README.md` and `schemas/mve_evidence.schema.json` for the expected evidence format. Then rerun:

```bash
python scripts/run_pipeline.py --falsification-only
```

## Main outputs

- `output/discovery_grounding.json/.md` — literature grounding, novelty/challenge maps, solution-level checks.
- `output/evolution_trace.json` — all persona variants and selected seeds.
- `output/attack_loop/IDEA-*/round_*/` — Phase 10–14 attack/revision history.
- `output/attack_loop_summary.json/.md` — provisional literature/reviewer survival.
- `output/falsification/IDEA-*/round_*/` — Phase 15–19 falsification artifacts.
- `output/falsification_summary.json/.md` — FINAL GREENLIGHT / READY_FOR_MVE / REVISE_EVIDENCE / KILL.
- `output/mve_evidence/` — externally executed MVE evidence supplied for verification.
- `output/survivor_elo.json/.md` — final-survivor relative ranking.
- `output/research_blueprints.json/.md` — full-study plans for final GREENLIGHT ideas only.
- `memory/ideation_memory.json` — feasible, MVE-ready, evidence-revision, and failed directions across runs.
- `output/FINAL_REPORT.md`, `dashboard.html`, `SESSION.md`, `SESSION.json`.

## Validation

```bash
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
```

The offline suite covers parsing/schema logic, discovery gates, attack-loop recurrence, direct-collision vetoes, quote-or-zero grounding, falsification contracts, no-evidence/no-GREENLIGHT behavior, evidence verdict mapping, final-survivor ELO, and memory states.

## Provenance

The Phase 10–14 adversarial prompts are the supplied research-review workflow preserved in `prompts/`. The discovery/evolution front end is an independent implementation informed by publicly documented EvoScientist/EvoSkills concepts. V5's falsification layer is an independent implementation informed by the Agents4Science examples emphasizing experiment-driven hypothesis testing, structured evidence, and separation between scientist agents and external evaluation. See `THIRD_PARTY_NOTES.md`.
