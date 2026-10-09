# Scientific gate definitions

| Status | Automatically set? | Meaning |
|---|---|---|
| HYPOTHESIS | Yes, S1 | A selected falsifiable statement, not a proven claim |
| CHECKED | Yes, S4 | Docker run returned valid expected slots and passed integrity checks; independent science review not performed |
| PROVISIONAL | Derived | Claim has checked supporting evidence, still requires external validation |
| VERIFIED evidence | **No** | Separate explicit verification of methods, data and independent support |
| INDEPENDENTLY REPRODUCED | **No** | Requires a separate controlled repeat and documented metric comparisons |
| PUBLICATION_READY | **Never** | Requires human/venue checks beyond this tool |

Integrity checks do not replace hypothesis feasibility assessment, sound split protocols, sample-size and power analyses, missing-data treatment, fair baselines, ablations, robustness studies, ethics and licensing, or citation verification. A run on a synthetic dataset must not be reported as clinical or real-world generalization. All quantitative sentences in manuscripts should be linked to explicit result IDs and to evidence that supports the exact claim strength.

ResearchLedger's `validate-paper` is designed for Markdown provenance markers; Paper Factory uses LaTeX. This release does **not** claim complete automatic sentence-level validation of the final LaTeX PDF. Evidence links and source results are recorded for further review.
