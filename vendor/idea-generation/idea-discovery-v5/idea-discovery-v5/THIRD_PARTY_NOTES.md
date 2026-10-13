# Third-Party Design Notes

This package contains independently implemented code.

The V4 discovery/evolution front end was informed at the architectural level by publicly documented EvoScientist / EvoSkills concepts reviewed on 2026-10-05, including literature grounding, challenge/insight mapping, problem-selection gates, persona-based evolution, pairwise ranking, and research memory.

V5's falsification layer was informed at the architectural level by the public Agents4Science teaching/examples repository reviewed on 2026-10-05. The specific principles adopted are separation between scientific agents and external evaluation, experiment-driven hypothesis testing, structured evidence rather than free-form confidence, and explicit comparison to hidden/held-out truth in simulation examples. V5 generalizes those principles to real research without pretending that real scientific truth is directly observable.

No Agents4Science code is copied into this package. The implementation here uses its own prompts, state transitions, evidence format, and conservative real-research verdicts (`SUPPORTED / INCONCLUSIVE / CONTRADICTED`, not oracle truth).

Before redistributing third-party code or assets from either upstream project, consult each upstream repository's current license and notices.
