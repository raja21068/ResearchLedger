---
name: paper-orchestra-outline
description: "ResearchLedger outline skill using vendored PaperOrchestra guidance and evidence-first rules."
---

# PaperOrchestra / Outline

## Research Method

Create an argument map from the real idea and supplied experimental protocol. Each section must have a question, main claim, required evidence, and approximate length. Reject results claims without named slots. Record unresolved methodological dependencies.

## Inputs

Existing manuscript state, available citations, study protocol and documented result slots. Do not claim external verification when source checks were not conducted.

## Reference

Read the [bundled upstream PaperOrchestra prompt](../../vendor/paperorchestra/methods/prompts/outline_agent.py) as methodological background. Apply [the master writing contract](../paper-orchestra/SKILL.md) in case of conflict, especially its prohibition on fabricated results and unverified references.

## Expected Output

Actionable, inspectable manuscript-stage artifacts and an explicit list of unresolved evidence dependencies.
