# `peer-review-panel` calibration fixture

A small, synthetic, **deliberately flawed** manuscript (`papers/main/paper.md`) with 5 planted
defects, one per reviewer persona in `peer-review-panel`, plus a deterministic scorer
(`scripts/score_review_panel.py`) so you can measure "did the review catch this" as a number
instead of a vibe — and use the *same* number to compare against another tool, including ARS.

## Why this exists

"Is my panel better than ARS's reviewer panel" isn't answerable by reading both READMEs — it needs
a manuscript with a known-correct answer key and the same scoring method applied to both outputs.
ARS's own repo makes the same point: its reviewer-calibration harness runs a held-out corpus
against a gold set and reports hit/false-positive rates rather than asserting quality. This fixture
is a much smaller version of that idea — one manuscript, five flaws — sized to actually run in a
single session rather than needing a corpus-scale eval infrastructure.

**Be honest about what this is and isn't.** n=1 fixture, keyword-substring scoring, not a
peer-reviewed benchmark. It tells you whether a specific known defect got flagged in roughly the
expected terms — it does not tell you review *quality* (tone, actionability, whether the synthesis
correctly prioritized). Read the actual review text, not just the scorecard, before drawing
conclusions. Treat this as a floor check and a fair head-to-head yardstick, not a leaderboard.

## The five planted flaws

| ID | Persona that should catch it | What's wrong |
|----|---|---|
| F1 | Methods & Reproducibility | Paper reports "97% accuracy across all clients"; the linked evidence/claim records show 97% is one outlier client, mean is 89.1% |
| F2 | Impact & Related-Work | Paper claims to be "first" to apply DP to federated learning; its own Related Work section cites two prior papers that already do this |
| F3 | Devil's Advocate | Proposed method trained 200 rounds vs. baseline's 80 rounds — an unmatched, unruled-out confound |
| F4 | Methods & Reproducibility | A causal claim is hedged ("results suggest") but has no statistical test, ablation, or control behind it — the hedge doesn't supply the missing evidence |
| F5 | Journal-Fit & Construct | "Client drift resilience" is the paper's own title term but is never operationally defined anywhere in the text |

Full detail and the exact trigger phrases the scorer looks for are in `flaws.json`.

## How to run it

**1. Review with ResearchLedger's panel:**

```text
cd examples/review-panel-calibration
claude --plugin-dir /path/to/ResearchLedger
# inside the session:
/research
> run a peer-review-panel review on papers/main/paper.md
```

Save the panel's full output (all four persona sections + synthesis) to a file, e.g.
`review-rl.md`.

**2. Score it:**

```bash
python3 scripts/score_review_panel.py review-rl.md --label "researchledger-panel"
```

**3. Run the same manuscript through ARS (or any other tool) and score that output too:**

```bash
python3 scripts/score_review_panel.py review-ars.md --label "ars-reviewer"
```

Now you have two scorecards over the identical input, scored the identical way — an actual
comparison, not a README claim. If a tool misses a flaw, read its review text for that section
first; the scorer only knows the phrasings listed in `flaws.json`, so a real catch worded
differently will show as a false MISS.

## Extending this fixture

Real signal comes from more than one fixture. If you want a firmer answer than n=1:

- Add a second and third synthetic manuscript (or de-identified excerpts of your own past drafts,
  before you noticed the issues) with their own `flaws.json`, and average hit-rate across all of
  them.
- Keep each fixture's flaws tied to a specific persona so a low score tells you *which* reviewer
  mandate is underperforming, not just that something is off.
- If you do this, consider whether the trigger-phrase list is fair to both tools — a phrase list
  hand-tuned only to ResearchLedger's typical wording would bias the comparison in its favor.
