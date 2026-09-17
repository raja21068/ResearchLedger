# quickstart example workspace

A tiny, real ResearchLedger v2 workspace, shipped so you (or CI) can point `researchledger` at
something real instead of an empty directory. From this directory:

```bash
researchledger validate --strict   # PASS, 0 warnings, 0 errors, every metric at 100%
researchledger report
researchledger trace C001          # paper.md -> C001 -> E001 -> R0001/R0002 -> metrics -> hash
researchledger validate-paper papers/main/paper.md
```

It tells one honest, complete story: a baseline classifier's accuracy claim (`C001`), backed by
one evidence record (`E001`) that only reaches `verified` because it's corroborated across **two**
independent runs (`R0001` seed 42, `R0002` seed 43) — not because one run happened to work. `R0002`'s
manifest chains to `R0001`'s (`previous_run_hash`), demonstrating the tamper-evident run chain. One
decision (`D001`) records why the baseline was accepted, and `papers/main/paper.md` carries a
provenance marker (`<!-- rl:claim=C001 -->`) linking its one quantitative sentence back to `C001`.

**What this is not**: `command.txt` references `python train.py --seed 42 --config
configs/base.yaml`, but there's no real `train.py` here — the run manifests, environment, metrics
and artifact hashes are all real and internally consistent (that's what `validate --strict`
actually checks), but this is a fixture, not a live experiment. `researchledger reproduce R0001`
will try to run that command and fail, because there's nothing to run. See
[`../../reference/run-ledger.md`](../../reference/run-ledger.md) for the full spec this fixture
demonstrates.
