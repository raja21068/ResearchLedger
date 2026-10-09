# Contributor instructions

- Preserve the five-stage public contract: S1 idea, S2 draft, S3 review, S4 code, S5 refine.
- Every new output gate requires offline regression tests; never claim actual experiments ran from unit tests.
- Use `factory.config.validate_context` for new settings, and update README + example context.
- A stage may only be skipped with verified upstream **input** and artifact hashes.
- Avoid network access by default. Do not execute generated experimental source code on the host.
- Publication readiness is a manual/independent judgment; never equate review-score thresholds with proof of science.
- Run `python -m unittest discover -s tests -p 'test_*.py' -v` before publishing changes.
