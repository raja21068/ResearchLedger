"""JSON Schema validation for evidence/claim/decision/run instances.

Backed by the `jsonschema` package — no hand-rolled validator. Schemas live
in schemas/ at the repo root (see reference/run-ledger.md); this resolves
them relative to the installed researchledger package's own source
location, which works for the documented `pip install -e .` from a checkout
of this repo. A non-editable install elsewhere would need schemas/ shipped
separately — see the note in reference/run-ledger.md.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

import jsonschema

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


@cache
def _load_schema(name: str) -> dict:
    path = _SCHEMAS_DIR / f"{name}.schema.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Schema {name!r} not found at {path}. researchledger expects an editable "
            f"install (`pip install -e .`) from a checkout that still has its schemas/ "
            f"directory next to the researchledger/ package."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def validate_instance(name: str, instance: dict) -> list[str]:
    """Returns human-readable violation messages against schemas/<name>.schema.json.

    An empty list means the instance is valid.
    """
    schema = _load_schema(name)
    validator = jsonschema.Draft7Validator(schema)
    messages = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(map(str, e.path))):
        location = ".".join(str(p) for p in error.path) or "(root)"
        messages.append(f"{location}: {error.message}")
    return messages
