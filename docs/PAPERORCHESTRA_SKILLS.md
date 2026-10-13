# PaperOrchestra as built-in ResearchLedger skills

[Back to README](../README.md) · [No API keys with Claude Code/Codex](NO_API_KEY_CLAUDE_CODE_CODEX.md) · [Scientific integrity](SCIENTIFIC_READINESS.md)

## What changed

Previously Factory S2 would fail without the independent `~/.claude/skills/paper-orchestra/SKILL.md` installation, even though the repository included the original Google PaperOrchestra Python source in `vendor/paperorchestra/`.

Factory S2 now **prefers the repository's own skill** (`skills/paper-orchestra/SKILL.md`) and five companion stage skills. This makes checkout-based, editable installs self-contained at the skill-instruction level. `researchctl doctor` checks the first-party skill and original vendor prompt assets. Root-level `AGENTS.md` and `CLAUDE.md` also point the respective local CLI agents to the bundled skills. An explicit `skills_dir` override is still accepted; a broken override fails rather than silently falling back.

| Skill | Scope | Original PaperOrchestra reference |
| --- | --- | --- |
| [paper-orchestra](../skills/paper-orchestra/SKILL.md) | Full controlled writing workflow | [Upstream README](../vendor/paperorchestra/README.md) |
| [paper-orchestra-outline](../skills/paper-orchestra-outline/SKILL.md) | Evidence/section structure | `methods/prompts/outline_agent.py` |
| [paper-orchestra-literature](../skills/paper-orchestra-literature/SKILL.md) | Literature and unsupported-source checks | `methods/prompts/literature_review_agent.py` |
| [paper-orchestra-sections](../skills/paper-orchestra-sections/SKILL.md) | Venue-aware drafting | `methods/prompts/section_writing_agent.py` |
| [paper-orchestra-figures](../skills/paper-orchestra-figures/SKILL.md) | Conceptual figures vs. result-slot graphics | Figure guidance; **no invented metrics** |
| [paper-orchestra-refine](../skills/paper-orchestra-refine/SKILL.md) | Writing and evidence consistency | `methods/prompts/content_refinement_agent.py` |

## Two distinct implementation paths

1. **ResearchLedger skill-based writing (integrated):** `researchctl run` S2 asks the authenticated local `claude` or `codex` command to explicitly read the bundled skills and upstream prompt source, then produce the standard `workspace/final/paper.tex`. The Factory checks slot coverage, repairs and compiles. **No direct API key is required by this transport.** The CLI must exist and be authenticated on the same computer, and subscription usage is governed by each service's terms.
2. **Original vendored PaperOrchestra Python pipeline (bundled, not invoked by default):** the scripts under `vendor/paperorchestra/` use their own provider integrations and may require their own API credentials. Keeping the source files in the distribution does **not** mean the complete original Python pipeline has been executed.

There is no silent fallback from a failed CLI run to synthetic reviews or fake paper output.

## Start with an authenticated local CLI

```bash
python -m pip install -e .
claude auth status       # or: codex login status
researchctl doctor
researchctl init 'auditable agent systems'
# Edit the printed workspace's _inputs/topic.md and other study inputs.
```

Choose the writing CLI in `<workspace>/_inputs/context.json` (preserve existing keys):

```json
{
  "writer_provider": "codex",
  "writer_timeout": 5400
}
```

Use `"writer_provider": "claude"` to choose Claude Code. The writer is **not** a PDF-only reviewer; to use the iterative Beihang review engine select the separately configured `review_agent: "beihang-native"` workflow. The review configuration lives in [the no-API-key guide](NO_API_KEY_CLAUDE_CODE_CODEX.md).

Then run the project with `researchctl run --project auditable-agent-systems` (requires properly prepared idea, experiment toolchain and evidence inputs). See [START_HERE.md](../START_HERE.md) for exploration versus protocol-locked validation setup.

## Protected research outputs

- S2 deliberately drafts *before* S4 executes code. Every empirical value is a `\PFVAL{id}` placeholder and every results figure is `\PFFIG{id}` until linked measurements exist.
- A completed PDF is a formatted artifact, **not** an independently verified scientific study.
- A model-generated literature section must flag sources and claims it did not verify against the actual originals. Crossref metadata alone cannot establish citation support or novelty.
- The skill does not authorize running generated experimental code on the host. S4 continues to use the restricted Docker sandbox.
- The original vendored source is kept intact, with its Apache 2.0 license; adaptation is limited to writing skills and Factory integration.

## What was actually tested

Offline automated tests cover: bundled skill discovery; stage-skill reference files; explicit override failures; missing-vendor detection; doctor reporting; Codex CLI argument/stdin behavior using a local **stub**; Factory draft contract; and existing reviewer/idea bridge tests. **These are software integration tests, not real Claude/Codex manuscript-quality evaluations.**

## Additional engineering improvements worth doing

| Priority | Improvement | Acceptance test |
| --- | --- | --- |
| P0 | Bind each paragraph-level research claim to a ledger evidence ID | Reject/result in warning for unbound quantitative assertions in compiled draft |
| P0 | Run real Beihang review on the final PDF, not just LaTeX text | Persist independent reviews, manuscript version, concern anchors, and closure state |
| P0 | Turn literature references into a verified source register | Every cited DOI has metadata; every *substantive* source-support claim is either checked or explicitly unresolved |
| P1 | Separate planning from publication-oriented writing | Draft result-neutral outlines first, write interpretations only after measurement gates |
| P1 | Extract citations/figures from vendor prompts into reusable skill tests | Regression fixtures check stages generate expected file layout and scientific constraints |
| P1 | Resume only affected writing sections after a failed review | Checkpoint hashes identify revisions without overwriting valid artifacts |
| P2 | Domain-specific writing profiles for medical AI, behavioral science, systems research | Distinct rubrics and venue/ethics checks with fixtures and reference manuscripts |

**Claim policy:** No publication readiness, measured improvement in writing quality, or scientific superiority is inferred from these integration tests.
