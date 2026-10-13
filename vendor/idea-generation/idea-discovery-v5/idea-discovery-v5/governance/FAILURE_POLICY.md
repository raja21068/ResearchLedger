# Failure / Degradation Policy

- API transport failures are retried according to `config/settings.json`.
- Malformed model JSON is locally parsed where safe, then re-requested as corrected JSON.
- Schema-invalid model output is repaired/re-requested; it is not silently accepted.
- Semantic invariant violations are recorded as `_validation_warnings` in artifacts.
- Embedding/model-download failure degrades to LLM-only clustering.
- Knowledge-graph failure does not delete other clustering evidence.
- Semantic Scholar/Crossref/OpenAlex/arXiv failures produce incomplete/unverified evidence; they never produce a false `VERIFIED` state.
- Human checkpoint rejection removes the gap before idea generation.
- The iterative attack loop can kill an idea even if an upstream score or prior round was strong; every material revision must survive Phases 10–13 again.
