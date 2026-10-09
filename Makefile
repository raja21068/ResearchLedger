.PHONY: doctor test test-all

doctor:
	python -m factory.cli.main doctor

test:
	python -m unittest discover -s tests -p 'test_*.py' -v

test-all:
	python -m pytest -q tests tests_researchledger
