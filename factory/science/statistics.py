"""Descriptive multi-seed checks, not automatic statistical significance claims."""
from __future__ import annotations
import math
from statistics import mean, stdev
from factory.results import read_results


def summarize(payload, *, primary_metric, seeds):
    issues = []
    groups = payload.get('seed_metrics')
    if not isinstance(groups, dict):
        return {'status': 'BLOCKED', 'issues': ['seed_metrics must be a dictionary keyed by metric ID']}
    if primary_metric not in groups:
        issues.append('primary metric missing from per-seed evidence')
    reported = payload.get('values', {})
    stats = {}
    for key, values in groups.items():
        if key not in reported:
            issues.append(f'{key}: no matching reported aggregate metric')
            continue
        if not isinstance(values, list) or len(values) != len(seeds) or len(values) < 2:
            issues.append(f'{key}: must include one result per registered random seed')
            continue
        if any(type(x) not in (int,float) or not math.isfinite(x) for x in values):
            issues.append(f'{key}: non-finite or non-numeric seed result')
            continue
        avg = mean(values)
        if not math.isclose(avg, reported[key], abs_tol=1e-6, rel_tol=1e-6):
            issues.append(f'{key}: reported aggregate differs from arithmetic mean of seeds')
        stats[key] = {'mean': avg, 'sample_standard_deviation': stdev(values),
                      'number_of_seeds': len(values)}
    return {'status': 'PASS' if not issues else 'BLOCKED', 'issues': issues,
            'summary': stats, 'limitation': 'This is descriptive seed variability, not an inferential confidence interval.'}


def audit(project):
    import json
    from pathlib import Path
    from factory.science.protocol import PROTOCOL, check
    project = Path(project).resolve()
    ok, issues = check(project, {'science_mode': 'validation'})
    if not ok:
        return {'status': 'BLOCKED', 'issues': issues}
    try:
        spec = json.loads((project / PROTOCOL).read_text())
        result = read_results(project / '4_code/results.json')
        if result.get('scale') != 'validation_data_attempt':
            return {'status':'BLOCKED', 'issues':['experiment is not a validation-data attempt']}
        return summarize(result, primary_metric=spec['design']['primary_metric'],
                         seeds=spec['design']['random_seeds'])
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return {'status': 'BLOCKED', 'issues': [str(exc)]}
