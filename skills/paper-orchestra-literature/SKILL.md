---
name: paper-orchestra-literature
description: "ResearchLedger literature skill using vendored PaperOrchestra guidance and evidence-first rules."
---

# PaperOrchestra / Literature

## Research Method

Keep a prior-work matrix with source identifier, bibliographic lookup status, full-text checked?, proposition support checked?, nearest competitor, and precise remaining gap. Use scholarly sources only when genuinely retrieved; avoid made-up DOI/BibTeX. Distinguish metadata from demonstrated novelty.

## Inputs

Existing manuscript state, available citations, study protocol and documented result slots. Do not claim external verification when source checks were not conducted.

## Reference

Read the [bundled upstream PaperOrchestra prompt](../../vendor/paperorchestra/methods/prompts/literature_review_agent.py) as methodological background. Apply [the master writing contract](../paper-orchestra/SKILL.md) in case of conflict, especially its prohibition on fabricated results and unverified references.

## Expected Output

Actionable, inspectable manuscript-stage artifacts and an explicit list of unresolved evidence dependencies.
