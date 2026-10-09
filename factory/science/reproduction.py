"""Isolated repeat of an imported S4 experiment; never run generated code on host."""
from __future__ import annotations

import json
import math
from pathlib import Path

from factory.io import atomic_json
from factory.pipeline.provenance import hash_file
from factory.steps.code import tree_hash
from factory.results import read_results
from factory.integrations.ledger import verify_run_receipt
from factory.sandbox import Sandbox

RECEIPT = 'control/independent_repeat.json'
OUT = 'control/independent_repeat_output/run/results.json'
# A reproduction comparison must never become a vacuous match because the
# caller specified effectively infinite tolerances. Research-specific
# tolerances tighter than these caps remain the investigator's responsibility.
MAX_ABSOLUTE_TOLERANCE = 0.01
MAX_RELATIVE_TOLERANCE = 0.01


def _valid_tolerances(abs_tol, rel_tol):
    return all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= (MAX_ABSOLUTE_TOLERANCE if i == 0 else MAX_RELATIVE_TOLERANCE)
               for i, x in enumerate((abs_tol, rel_tol)))


def _safe_evidence_path(root, path):
    """Reject symlink components, not just a symlink at the final path."""
    root, path = Path(root).absolute(), Path(path).absolute()
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return not any(item.is_symlink() for item in (root, *[root / Path(*relative.parts[:i])
                                                     for i in range(1, len(relative.parts) + 1)]))


def _compare(reference, observed, *, abs_tol, rel_tol):
    errors = []
    rv, ov = reference.get('values', {}), observed.get('values', {})
    rs, os = reference.get('series', {}), observed.get('series', {})
    if set(rv) != set(ov) or set(rs) != set(os):
        errors.append('result value or series IDs changed')
    for key in sorted(set(rv) & set(ov)):
        if not math.isclose(rv[key], ov[key], rel_tol=rel_tol, abs_tol=abs_tol):
            errors.append(f'{key}: numeric mismatch ({rv[key]} vs {ov[key]})')
    for key in sorted(set(rs) & set(os)):
        a, b = rs[key], os[key]
        if a.get('x') != b.get('x') or set(a.get('series', {})) != set(b.get('series', {})):
            errors.append(f'{key}: axes or curve names changed')
            continue
        for curve, vals in a['series'].items():
            oth = b['series'][curve]
            if len(vals) != len(oth) or any(not math.isclose(x, y, rel_tol=rel_tol, abs_tol=abs_tol)
                                            for x, y in zip(vals, oth)):
                errors.append(f'{key}/{curve}: numeric series mismatch')
    if reference.get('scale') == 'validation_data_attempt':
        a, b = reference.get('seed_metrics', {}), observed.get('seed_metrics', {})
        if not isinstance(a, dict) or not isinstance(b, dict) or set(a) != set(b):
            errors.append('per-seed metric keys changed')
        else:
            for metric in a:
                x, y = a[metric], b[metric]
                if (not isinstance(x, list) or not isinstance(y, list) or len(x) != len(y) or
                        any(type(p) not in (int, float) or type(q) not in (int, float) or
                            not math.isfinite(p) or not math.isfinite(q) or
                            not math.isclose(p, q, rel_tol=rel_tol, abs_tol=abs_tol)
                            for p, q in zip(x, y))):
                    errors.append(f'{metric}: per-seed result mismatch')
        for key in ('data_source', 'seeds', 'n_samples'):
            if reference.get(key) != observed.get(key):
                errors.append(f'{key}: attestation changed in repeated run')
    return errors


def repeat(project, context=None, *, abs_tol=1e-7, rel_tol=1e-5, sandbox=None):
    project = Path(project).resolve()
    if not _valid_tolerances(abs_tol, rel_tol):
        raise ValueError('comparison tolerances must be finite, nonnegative and at most 0.01')
    from factory.pipeline.lock import exclusive_run
    with exclusive_run(project):
        valid, note = verify_run_receipt(project)
        if not valid:
            raise ValueError('original experiment has invalid evidence: ' + note)
        source = read_results(project / '4_code/results.json')
        receipt = json.loads((project / 'control/ledger_s4_receipt.json').read_text(encoding='utf-8'))
        repo = project / '4_code/repo'
        if repo.is_symlink() or any(p.is_symlink() for p in repo.rglob('*')):
            raise ValueError('unsafe generated repository')
        if tree_hash(repo) != source.get('repo_sha256'):
            raise ValueError('generated repository altered')
        image = source['image']
        sandbox = sandbox or Sandbox(image, allow_network_install=False)
        if sandbox.image != image:
            raise ValueError('reproduction must use the same pinned container image')
        folder = project / 'control/independent_repeat_output'
        if folder.is_symlink():
            raise ValueError('unsafe reproduction output directory')
        folder.mkdir(parents=True, exist_ok=True)
        # Refuse stale output from a previous attempt, but preserve its receipt in history.
        from shutil import rmtree
        deps = folder / 'deps'
        output = folder / 'run'
        for path in (deps, output):
            if path.is_symlink():
                raise ValueError('unsafe output/dependency symlink')
            if path.exists():
                rmtree(path)
        install = sandbox.install(repo, deps)
        if install.get('status') == 'FAIL':
            raise ValueError('isolated reproduction dependency installation failed')
        data = project / '_inputs/data'
        execution = sandbox.run(repo, source.get('command', ['python', 'pf_run.py']), output,
                                deps=deps, data=data if data.is_dir() else None,
                                timeout=int((context or {}).get('code_timeout', 3600)))
        if execution.get('status') != 'PASS' or execution.get('returncode') != 0:
            raise ValueError('isolated repetition failed; no reproduction receipt issued')
        observed = read_results(output / 'results.json')
        problems = _compare(source, observed, abs_tol=abs_tol, rel_tol=rel_tol)
        report = {'schema_version': 1, 'run_id': receipt['run_id'],
                  'source_results_sha256': hash_file(project / '4_code/results.json'),
                  'repo_sha256': tree_hash(repo), 'image': image,
                  'dataset_sha256': __import__('factory.integrations.ledger', fromlist=['_dataset_hash'])._dataset_hash(project),
                  'repeated_results_sha256': hash_file(output / 'results.json'),
                  'comparison': {'abs_tol': abs_tol, 'rel_tol': rel_tol, 'problems': problems},
                  'status': 'MATCHED_WITHIN_TOLERANCE' if not problems else 'MISMATCH',
                  'scientific_status': 'ONE_ISOLATED_REPEAT_ONLY_NOT_INDEPENDENT_VERIFICATION'}
        atomic_json(project / RECEIPT, report)
        return report


def check(project):
    project = Path(project).resolve()
    path = project / RECEIPT
    out = project / 'control/independent_repeat_output/run/results.json'
    try:
        if (not _safe_evidence_path(project, path) or not _safe_evidence_path(project, out)
                or not path.is_file() or not out.is_file()):
            return False, ['reproduction report or output missing/unsafe']
        record = json.loads(path.read_text(encoding='utf-8'))
        comparison = record.get('comparison')
        if (not isinstance(comparison, dict) or
                not _valid_tolerances(comparison.get('abs_tol'), comparison.get('rel_tol'))):
            return False, ['unsafe or malformed reproduction tolerances']
        if record.get('status') != 'MATCHED_WITHIN_TOLERANCE':
            return False, ['isolated repeat does not match original result']
        valid, detail = verify_run_receipt(project)
        if not valid:
            return False, ['original experiment changed: ' + detail]
        from factory.integrations.ledger import _dataset_hash
        source = read_results(project / '4_code/results.json')
        checks = {'source_results_sha256': hash_file(project / '4_code/results.json'),
                  'repo_sha256': tree_hash(project / '4_code/repo'),
                  'image': source.get('image'), 'dataset_sha256': _dataset_hash(project),
                  'repeated_results_sha256': hash_file(out),
                  'run_id': json.loads((project / 'control/ledger_s4_receipt.json').read_text())['run_id']}
        if any(record.get(key) != value for key, value in checks.items()):
            return False, ['reproduction receipt stale or artifact tampered']
        actual = _compare(source, read_results(out),
                          abs_tol=record['comparison']['abs_tol'],
                          rel_tol=record['comparison']['rel_tol'])
        if actual or record['comparison']['problems'] != actual:
            return False, actual or ['stored comparison contradicts recomputed comparison']
        return True, []
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return False, [str(exc)]
