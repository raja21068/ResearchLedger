# V4 Change Log

## Added

- 30–50-paper discovery-grounding target with bounded saturation search.
- Novelty tree (Type 1–4) and challenge→insight tree before ideation.
- Four-level well-established-solution gate; Levels 1/2 are blocked, Levels 3/4 may proceed.
- Quote-or-zero evidence validation for solution-level judgments.
- Fail-closed behavior when the grounded pool is below the configured minimum.
- Three-track idea generation and Innovator/Pragmatist/Critic evolution over configurable iterations.
- Persistent evolution trace preserving all persona variants.
- Survivor-only Elo ranking after GREENLIGHT.
- Cross-run ideation memory for feasible directions and dead ends.
- V4 final report/session/dashboard integration.
- Third-party design/provenance notes.

## Preserved from V3.1

- Phase 10 weighted scientific scorecard.
- Phase 11 destructive novelty attack.
- Phase 12 novelty matrix and intellectual-contribution test.
- Phase 13 Reviewer #1 rejection attack.
- Phase 14 revise/pivot/kill.
- Mandatory return to Phase 10 after material revision.
- Fresh literature search on each revised idea.
- Direct-collision/fatal-flaw blocking.
- Fail closed after maximum attack rounds.

## Engineering hardening

- New deterministic tests for solution-level filtering, quote evidence, survivor-only Elo, Elo arithmetic, and cross-run memory.
- V4 version labels propagated through report/session/dashboard and API user-agent strings.
