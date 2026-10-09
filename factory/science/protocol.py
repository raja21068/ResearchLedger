"""Preregistered protocol gate. A checksum is a change detector, NOT a timestamp proof.

The protocol is explicitly operator-authored. An exploratory project cannot become
confirmatory retrospectively without a new, disclosed prospective protocol.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

from factory.io import atomic_json
from factory.pipeline.provenance import hash_file
from researchledger.hashing import sha256_path

PROTOCOL = '_inputs/research_protocol.json'
LOCK = 'control/protocol_lock.json'
VALID_MODES = {'exploration', 'validation'}


def _read(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f'unsafe symlink: {path}')
    if not path.is_file():
        raise ValueError(f'missing: {path}')
    result = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(result, dict):
        raise ValueError(f'{path.name} must be a JSON object')
    return result


def _data_digest(project):
    data = Path(project) / '_inputs/data'
    if not data.exists():
        return None
    if data.is_symlink() or any(item.is_symlink() for item in data.rglob('*')):
        raise ValueError('dataset may not contain symlinks')
    return sha256_path(data)


def scaffold(project):
    """Write a *blank* human-editable experimental contract; never invent methods."""
    path = Path(project) / PROTOCOL
    if path.exists() or path.is_symlink():
        raise ValueError('protocol exists: edit it rather than overwriting it')
    spec = {
        'schema_version': 1,
        'question': '', 'hypothesis': '', 'falsifier': '',
        'dataset': {'name': '', 'version': '', 'split_strategy': '', 'license_reviewed': False,
                    'source': '', 'unit_of_independence': ''},
        'design': {'primary_metric': '', 'primary_baseline': '', 'analysis_plan': '',
                   'ablation_plan': '', 'random_seeds': [], 'limitations': ''},
        'analysis_type': 'exploratory',
        'operator_acknowledgement': False,
    }
    atomic_json(path, spec)
    return {'path': str(path), 'status': 'NEEDS_OPERATOR_INPUT'}


def validate_spec(spec):
    issues = []
    if spec.get('schema_version') != 1:
        issues.append('schema_version must be 1')
    for key in ('question', 'hypothesis', 'falsifier'):
        if not isinstance(spec.get(key), str) or len(spec[key].strip()) < 15:
            issues.append(f'{key}: provide a concrete statement of at least 15 characters')
    for parent, fields in (('dataset', ('name', 'version', 'split_strategy', 'source', 'unit_of_independence')),
                           ('design', ('primary_metric', 'primary_baseline', 'analysis_plan', 'ablation_plan', 'limitations'))):
        section = spec.get(parent)
        if not isinstance(section, dict):
            issues.append(f'{parent}: expected object')
            continue
        for key in fields:
            if not isinstance(section.get(key), str) or not section[key].strip():
                issues.append(f'{parent}.{key}: required')
    ds = spec.get('dataset', {})
    if not isinstance(ds, dict) or ds.get('license_reviewed') is not True:
        issues.append('dataset.license_reviewed: operator confirmation required')
    design = spec.get('design', {})
    seeds = design.get('random_seeds') if isinstance(design, dict) else None
    if not isinstance(seeds, list) or len(seeds) < 2 or any(type(x) is not int or x < 0 for x in seeds) or len(set(seeds)) != len(seeds):
        issues.append('design.random_seeds: at least two distinct nonnegative integers required')
    if spec.get('analysis_type') != 'confirmatory':
        issues.append('analysis_type: set to confirmatory before a validation-mode lock')
    if spec.get('operator_acknowledgement') is not True:
        issues.append('operator_acknowledgement: operator confirmation required')
    return issues


def lock(project):
    project = Path(project).resolve()
    file = project / PROTOCOL
    dest = project / LOCK
    if dest.exists() or dest.is_symlink():
        raise ValueError('protocol already locked; create a new project/protocol version to change it')
    spec = _read(file)
    issues = validate_spec(spec)
    if issues:
        raise ValueError('cannot lock protocol: ' + '; '.join(issues))
    idea = project / '1_idea/idea.md'
    if not idea.is_file() or idea.is_symlink():
        raise ValueError('select and record an idea in S1 before locking the protocol')
    digest = _data_digest(project)
    if digest is None or not any(p.is_file() for p in (project / '_inputs/data').rglob('*')):
        raise ValueError('validation requires a real dataset directory; synthetic-only pilots belong in exploration mode')
    receipt = {'schema_version': 1, 'locked_at_utc': datetime.now(timezone.utc).isoformat(),
               'protocol_sha256': hash_file(file), 'idea_sha256': hash_file(idea),
               'data_sha256': digest,
               'note': 'File-integrity lock only; not proof of prospective public preregistration'}
    atomic_json(dest, receipt)
    return receipt


def check(project, context, *, required=False):
    """(pass, problems) with no implicit promotion from exploration to validation."""
    mode = (context or {}).get('science_mode', 'exploration')
    if mode not in VALID_MODES:
        return False, ['invalid science_mode']
    if mode == 'exploration' and not required:
        return True, ['exploration only: no confirmatory or publication-readiness certification']
    project = Path(project).resolve()
    try:
        spec = _read(project / PROTOCOL)
        receipt = _read(project / LOCK)
        issues = validate_spec(spec)
        if (receipt.get('schema_version') != 1 or receipt.get('protocol_sha256') != hash_file(project / PROTOCOL)):
            issues.append('protocol modified or lock malformed')
        idea = project / '1_idea/idea.md'
        if not idea.is_file() or idea.is_symlink() or receipt.get('idea_sha256') != hash_file(idea):
            issues.append('selected idea changed since protocol lock')
        if receipt.get('data_sha256') != _data_digest(project):
            issues.append('input dataset changed since protocol lock')
        return not issues, issues
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return False, [str(exc)]
