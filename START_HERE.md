# Start here: Paper Factory × ResearchLedger 2.0.1 (audited)

This is the evidence-first update to the integrated research automation system. Its validation option adds **prospective protocol locks, DOI metadata checking, declared claim-to-result bindings, descriptive seed-statistics checks and isolated Docker repeats**. Passing automated checks does **not** establish novelty, scientific correctness, independent reproduction, or Q1 publication readiness.

## Install

Projects are placed under `~/.local/share/paperfactory/workspaces/` unless `PAPERFACTORY_WORKSPACES` is set or an existing checkout-local `workspaces/` directory is present. Use the location printed by `researchctl init`.

```bash
python -m pip install -e .
researchctl doctor
researchctl init "your research idea"
```

For a fast pilot, add `_inputs/topic.md` and use `researchctl run --project your-research-idea`. The default is `science_mode="exploration"`; outputs are exploratory/pilot-only.

For a controlled study, **set `"science_mode": "validation"` in the newly created `_inputs/context.json` before the first research run**. Then follow the sequence in [docs/EVIDENCE_FIRST_V2.md](docs/EVIDENCE_FIRST_V2.md): select idea, register protocol and real data, lock it, check DOI/prior art, generate results, bind all required quantitative claims, repeat experiment in isolated Docker, audit and refine.

Most useful commands: `researchctl protocol lock PROJECT`, `researchctl literature verify PROJECT --doi DOI`, `researchctl claims scaffold PROJECT`, `researchctl claims bind PROJECT`, `researchctl reproduce-isolated PROJECT`, and `researchctl science-audit PROJECT`.

This installation retains the original Paper Factory 5-stage execution architecture and ResearchLedger commands. It does not re-run generated code on the host.
