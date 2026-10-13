# Use ResearchLedger with Claude Code or Codex (without project API keys)

This is a **local, authenticated CLI** workflow, not a hosted ChatGPT/Codex integration. Logging into ChatGPT or Claude on a browser does not automatically provide CLI authentication in another environment. The command-line tools must exist **on the same computer executing ResearchLedger** and must be logged in. Subscription usage eligibility, quotas and terms are determined by the respective service. No API keys need to be placed in ResearchLedger project files.

## Check prerequisites

```bash
python -m pip install -e '.[dev,referee,idea-discovery]'

# Claude Code CLI: install and authenticate according to official Claude Code documentation
claude --version
claude auth status

# OR Codex CLI: install and authenticate according to official Codex documentation
codex --version
codex login status
```

The binaries must be discoverable using `PATH`. A missing, unauthenticated or failing CLI is a **blocking error**: there is no silent fallback to scripted model responses.

## 1. Idea Discovery V5 through your local subscription login

```bash
researchctl init 'trustworthy LLM agents'
researchctl idea-discovery prepare trustworthy-llm-agents
researchctl idea-discovery run trustworthy-llm-agents \
  --provider codex \
  --topic 'Falsifiable evaluations of agent-based scientific workflow integrity' \
  --paper ./prior_work.pdf
researchctl idea-discovery phase-audit trustworthy-llm-agents --idea-id IDEA-001
```

Replace `codex` with `claude` to use Claude Code. V5's **original phases and scientific gates** remain in place. The initial vendored ZIP is preserved, while a transparent `RESEARCHLEDGER_SUBSCRIPTION_CLI_SHIM_v1` is added to a *prepared per-project copy* of `scripts/utils.py` only when a CLI run is requested. A dry run does not execute models:

```bash
researchctl idea-discovery run trustworthy-llm-agents --provider codex \
  --topic 'Integrity of LLM-agent research workflows' --paper ./prior_work.pdf --dry-run
```

A V5 novelty score is not verified novelty. In particular, Phase 17–19 requires independently reviewed and executed evidence, not just a positive model rationale. The CLI transport does not automatically execute the proposed experiments.

## 2. Native Beihang Referee + senior-review prompt

```bash
researchctl referee cycle trustworthy-llm-agents ./paper_v1.pdf \
  --provider codex --pipeline full --mode deep --scorecard
```

This invokes the actual **Beihang Referee v0.1.0** Python engine with its core reviewer and independent verifier, adds the packaged senior-review rubric, and checks review/report invariants. External scholarly search may require Internet connectivity and additional permissions; it cannot be guaranteed simply by using a CLI login.

To compare authored manuscript versions:

```bash
researchctl referee cycle trustworthy-llm-agents \
  ./paper_v1.pdf ./paper_v2.pdf ./paper_v3.pdf \
  --provider codex --pipeline full --mode deep --scorecard
```

This **compares supplied drafts; it does not write revisions**. The Factory path below supports guarded automated revisions.

## 3. Factory automatic revision → rebuild → re-review loop

Set these keys in the existing project `_inputs/context.json`, preserving other keys such as `ledger_enabled` and `science_mode`:

```json
{
  "review_agent": "beihang-native",
  "referee_provider": "codex",
  "review_provider": "codex",
  "review_max_rounds": 4,
  "referee_pipeline": "full",
  "referee_mode": "deep",
  "referee_scorecard": true,
  "referee_search_backend": "federated"
}
```

Then, after providing required project inputs and any scientific measurements:

```bash
researchctl run --project trustworthy-llm-agents
researchctl audit trustworthy-llm-agents
researchctl science-audit trustworthy-llm-agents
```

The Factory review loop passes admitted concerns into the guarded LaTeX editor, rebuilds the draft, runs the real native reviewer on the changed PDF and inspects closure metadata. **Never interpret an automatic zero-concern status, a rubric score or a successful CLI invocation as proof of publication readiness or independent scientific correctness.** Review the actual source texts, data, claim binding, references and revised PDF yourself.

## 4. Where the prompts go

- Beihang original reviewer prompt and independent verifier remain in the vendored code.
- `factory/steps/review_assets/senior_review_rubric.txt` contains the supplied 20+ category reviewer instructions and is appended to the core reviewer's trusted prompt.
- Each run retains the rubric SHA-256 and evidence/report artifacts. The CLI is a **transport**; it does not replace review rules or short-circuit concern admission.
- The Idea Discovery V5 prompts are not replaced by a generic one-shot idea prompt. Its original phases are run by the native scripts.

## 5. Verified versus not yet verified (12 October 2026)

| Property | Evidence |
| --- | --- |
| Claude Code/Codex CLI invocation structure | Offline fake-CLI tests and syntax checks |
| Local V5 shim insertion without changing original ZIP | Offline tests |
| Existing scripted Beihang pipeline and prompt combination | Offline integration tests |
| Actual Claude Code/Codex model-backed review of a manuscript | **Not executed in the hosted environment** — CLI binaries/login unavailable |
| Scientific accuracy improvement | **Not established**; needs full-paper expert evaluation |
| Full regression suite | See release report; do not infer success from focused tests |

**Privacy:** A logged-in CLI still sends manuscript text to the selected provider. Use only authorized manuscripts and comply with your organization's research/data protection requirements. The CLI bridge runs in review-only modes (`claude` in plan mode with file-writing tools disallowed, `codex` in read-only sandbox) and sends prompts via stdin. It does not create or persist credentials.

## 6. Self-contained PaperOrchestra writing skills

Factory S2 now uses the bundled `skills/paper-orchestra/SKILL.md` with five stage skills and original source prompts under `vendor/paperorchestra/`. It no longer requires separately copying the skill into `~/.claude/skills`. Set `"writer_provider": "claude"` or `"writer_provider": "codex"` in `_inputs/context.json` to choose your local authenticated subscription CLI for writing. See [PaperOrchestra skills guide](PAPERORCHESTRA_SKILLS.md). The upstream API-based Python runtime is bundled as source only, not silently invoked.
