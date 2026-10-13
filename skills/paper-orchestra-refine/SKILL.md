---
name: paper-orchestra-refine
description: "ResearchLedger content refinement skill using vendored PaperOrchestra guidance and evidence-first rules."
---

# PaperOrchestra / Content Refinement

## Research Method

Check argument consistency, evidence boundaries, correct citations, method/claim alignment, results-slot preservation, venue style and LaTeX compilability. Maintain an unresolved concern register and do not turn unsupported claims into established findings.

## Inputs

Existing manuscript state, available citations, study protocol and documented result slots. Do not claim external verification when source checks were not conducted.

## Reference

Read the [bundled upstream PaperOrchestra prompt](../../vendor/paperorchestra/methods/prompts/content_refinement_agent.py) as methodological background. Apply [the master writing contract](../paper-orchestra/SKILL.md) in case of conflict, especially its prohibition on fabricated results and unverified references.

## Expected Output

Actionable, inspectable manuscript-stage artifacts and an explicit list of unresolved evidence dependencies.
