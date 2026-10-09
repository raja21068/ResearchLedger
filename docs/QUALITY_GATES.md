# Scientific validity and evidence gates

| Gate | Automatable evidence | What it **does not** prove |
|---|---|---|
| S1 selection | At least two scored candidate reviews; numeric falsifier | Novelty or feasibility validated by literature |
| S2 draft | Compiles and covers each result placeholder | References/claims are true, all numbers independently sourced |
| S3 review | Structured review and scored dimensions | Independent peer review or journal acceptance |
| S4 code | Syntax guard, no repo symlinks, successful Docker exit, complete schema slots | Correct algorithm, honest synthetic data, statistical validity |
| S5 refine | Reported improvement and all chosen mean thresholds reached | Q1 quality, reproducibility, ethical compliance |
| `researchctl audit` | Enumerates missing provenance and manual review requirements | Publication readiness certification |

## Minimum author checklist before journal submission

- Link each result and plotted panel to an experiment, dataset version, code commit, seed and independent reproduction log.
- Run intended **full-size** experiments; label pilot/synthetic results prominently and do not generalize beyond their scope.
- Validate baselines, ablations, uncertainty intervals, statistical tests, and design assumptions; avoid using a score target in place of effect validity.
- Check all bibliography entries and nearest-prior-art claims against primary source text.
- Verify dataset use permissions, consent/IRB as applicable, conflicts, funder acknowledgements and venue requirements.
- Get an independent human domain/technical review. Keep a dated evidence ledger for all claims.
