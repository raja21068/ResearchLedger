.PHONY: test validate manifest serve benchmark

test:
	pytest -q

manifest:
	python scripts/rebuild_package_metadata.py

validate: manifest
	python scripts/validate_package.py

serve:
	referee serve

benchmark:
	referee benchmark evals/cases/major_comment_cases.json
