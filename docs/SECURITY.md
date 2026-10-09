# Security considerations

**Threat boundary:** manuscript text, papers found on the web, model-generated LaTeX, requirements, generated code, and third-party vendor components are untrusted. Do not treat model instructions or a high score as verification.

## Implemented controls

- No workspace path traversal or symlinked project root through the supported CLI.
- Exclusive workspace run lock; separate historical and verified state; atomic checkpoint writes.
- SHA-256 checks of inputs and upstream outputs to detect staleness.
- Docker experiment execution: digest-pinned base image, network disabled, read-only repository, no added capabilities, `no-new-privileges`, CPU/memory/PID limits, read-only root filesystem and tmpfs.
- Docker package installation also has network **disabled by default**; enable only by explicit config. Generated requirements can execute untrusted install hooks even inside Docker.
- Refuse generated-repository symlinks, unexpected result IDs, nonfinite numeric values and oversized plots.
- LaTeX runs with `-no-shell-escape`, but this alone does **not** make arbitrary TeX safe.

## Important residual risks

- A Docker container is a security boundary with limits, not a perfect guarantee. Never mount credentials or writable host directories unnecessarily.
- Dependency installation with `allow_network_install=true` enables outbound network from the install container. Inspect every dependency first; pin versions, prefer local vetted wheels, and use a dedicated machine/VM for untrusted code.
- Claude Code S2 is allowed restricted shell commands to build and search literature. External pages and model-authored skill instructions are not trusted. Running Claude Code with broad personal file permissions increases the blast radius.
- `code_mode=pipeline` executes vendored third-party Python scripts **on the host**; the code the scripts generate is intended for Docker, but the pipeline itself is not sandboxed.
- Model-generated TeX/PDF compilation runs on the host. For hostile documents compile in a dedicated VM or hardened container; do not use privileged shell escape.
- Downloaded third-party vendor projects have their own security and licensing obligations. Audit them before publication or deployment.
- The model could implement incorrect methods and report spurious but validly formatted numbers. Use independent validation and real dataset/protocol checks.
- This project does not implement robust secrets management, enterprise authorization, or supply-chain signatures.

## Recovery

If `control/run.lock` remains after an abnormal exit, check that no controller is running before manually deleting it. To rebuild trust after changing source, inputs, prompts, or results, run `researchctl resume <slug>`. Old checkpoints without input SHA-256 are intentionally considered stale.
