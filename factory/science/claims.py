"""Claim-to-metric binding. This verifies arithmetic/provenance, not causal inference.

Explicit claims must be declared by an operator. Automatic extraction of every
scientific assertion from unrestricted prose is not claimed by this module.
"""
from __future__ import annotations

import math
import json
from pathlib import Path
from factory.io import atomic_json
from factory.pipeline.provenance import hash_file
from factory.results import read_results, load_spec
from factory.integrations.ledger import verify_run_receipt

CLAIMS = '_inputs/metric_claims.json'
BINDINGS = 'control/metric_claim_bindings.json'


def scaffold(project):
    project = Path(project)
    path = project / CLAIMS
    if path.exists() or path.is_symlink():
        raise ValueError('metric_claims.json exists; edit it directly')
    spec = load_spec(project / '2_paper/results_spec.json')
    rows = [{'id': 'MC_' + item['id'], 'statement': '', 'metric_id': item['id'],
             'direction': 'report_only', 'analysis': 'exploratory',
             'unit': '', 'population': '', 'note': 'describe the measured quantity, not an invented result'}
            for item in spec['slots'] if not item.get('optional')]
    atomic_json(path, {'schema_version': 1, 'claims': rows})
    return {'path': str(path), 'generated_claim_rows': len(rows), 'status': 'NEEDS_OPERATOR_INPUT'}


def _load(project):
    path = Path(project) / CLAIMS
    if path.is_symlink() or not path.is_file():
        raise ValueError('missing or unsafe _inputs/metric_claims.json')
    body = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(body, dict) or body.get('schema_version') != 1 or not isinstance(body.get('claims'), list):
        raise ValueError('metric_claims.json must have schema_version=1 and a claims list')
    return body


def evaluate(project, *, write=False):
    project = Path(project).resolve()
    ok, note = verify_run_receipt(project)
    if not ok:
        return {'status': 'BLOCKED', 'problems': ['ledger: ' + note]}
    try:
        contract = _load(project)
        result_path = project / '4_code/results.json'
        result = read_results(result_path)
        spec = load_spec(project / '2_paper/results_spec.json')
        required = {x['id']: x['kind'] for x in spec['slots'] if not x.get('optional')}
        present = set()
        used = set()
        problems = []
        attached = []
        for row in contract['claims']:
            if not isinstance(row, dict):
                problems.append('claim is not an object')
                continue
            id_, metric = row.get('id'), row.get('metric_id')
            if not isinstance(id_, str) or not id_.startswith('MC_') or id_ in used:
                problems.append('claim IDs must be unique MC_* identifiers')
                continue
            used.add(id_)
            if not isinstance(metric, str) or metric not in required:
                problems.append(f'{id_}: metric_id must reference a required result slot')
                continue
            present.add(metric)
            if not isinstance(row.get('statement'), str) or len(row['statement'].strip()) < 15:
                problems.append(f'{id_}: descriptive statement required')
            if not isinstance(row.get('population'), str) or not row['population'].strip():
                problems.append(f'{id_}: study population/dataset scope required')
            if row.get('analysis') not in ('exploratory', 'confirmatory'):
                problems.append(f'{id_}: analysis must be exploratory or confirmatory')
            if row.get('direction') not in ('report_only', 'higher', 'lower'):
                problems.append(f'{id_}: direction must be report_only, higher or lower')
            if required[metric] == 'value':
                number = result.get('values', {}).get(metric)
                if type(number) not in (int, float) or not math.isfinite(number):
                    problems.append(f'{id_}: metric {metric} missing or non-finite')
                    continue
                measurement = {'measured_value': number}
            else:
                series = result.get('series', {}).get(metric)
                if not isinstance(series, dict):
                    problems.append(f'{id_}: recorded series {metric} missing')
                    continue
                import hashlib
                measurement = {'series_sha256': hashlib.sha256(json.dumps(
                    series, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()}
            attached.append({'id': id_, 'metric_id': metric, **measurement,
                             'statement': row['statement'], 'analysis': row.get('analysis'),
                             'status': 'MEASURED_NOT_SCIENTIFICALLY_VERIFIED'})
        for missing in sorted(set(required) - present):
            problems.append(f'required result slot has no explicit claim binding: {missing}')
        from factory.integrations.ledger import RUN_RECEIPT
        origin = json.loads((project / RUN_RECEIPT).read_text(encoding='utf-8'))
        payload = {'schema_version': 1, 'claims_sha256': hash_file(project / CLAIMS),
                   'results_sha256': hash_file(result_path), 'run_id': origin['run_id'],
                   'claims': attached, 'status': 'PASS' if not problems else 'BLOCKED',
                   'problems': problems, 'coverage': 'DECLARED_RESULT_SLOTS_ONLY'}
        if write and not problems:
            atomic_json(project / BINDINGS, payload)
        return payload
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {'status': 'BLOCKED', 'problems': [str(exc)]}


def check(project):
    project = Path(project).resolve()
    target = project / BINDINGS
    if target.is_symlink() or not target.is_file():
        return False, ['missing metric claim binding receipt']
    try:
        old = json.loads(target.read_text(encoding='utf-8'))
        current = evaluate(project)
        if current.get('status') != 'PASS':
            return False, current.get('problems', [])
        if old != current:
            return False, ['metric claim binding receipt stale or tampered']
        return True, []
    except (OSError, ValueError, TypeError):
        return False, ['metric claim binding receipt invalid']
