# Executed MVE evidence

V5 never fabricates empirical verification. When an idea reaches `READY_FOR_MVE`, run the generated MVE protocol outside the pipeline, then place the real result here as:

`IDEA-001.json`

Minimum structure:

```json
{
  "idea_id": "IDEA-001",
  "executed": true,
  "protocol_version": "1",
  "executed_at": "2026-10-05T12:00:00Z",
  "environment": {"code_commit": "...", "hardware": "...", "seed_list": [1,2,3]},
  "results": {"primary_metric": "...", "baseline": "...", "effect": "...", "uncertainty": "..."},
  "controls": {"negative_control": "pass", "positive_control": "pass"},
  "leakage_checks": {"status": "pass"},
  "artifacts": ["results.csv", "config.yaml", "run.log"],
  "limitations": ["..."],
  "notes": "..."
}
```

Then run:

`python scripts/run_pipeline.py --falsification-only`

The independent verifier will assess the supplied evidence. Merely adding a file does not guarantee GREENLIGHT.
