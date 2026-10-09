"""Composed scientific release gates. Passing means automated integrity only."""
from __future__ import annotations
from factory.science import protocol, claims, literature, reproduction


def audit(project, context):
    mode = (context or {}).get('science_mode', 'exploration')
    result = {'science_mode': mode, 'scientific_status': 'NOT_INDEPENDENTLY_VERIFIED',
              'publication_ready': False, 'checks': {}}
    checks = {
        'protocol_locked': protocol.check(project, {'science_mode': 'validation'}),
        'claim_metrics_bound': claims.check(project),
        'isolated_repeat': reproduction.check(project),
    }
    if mode == 'validation':
        from factory.science.statistics import audit as statistical_audit
        stat = statistical_audit(project)
        checks['registered_seed_statistics'] = (stat['status'] == 'PASS', stat['issues'])
    lit = literature.audit(project)
    checks['literature_metadata_and_prior_art'] = (lit['status'] == 'PASS', lit['issues'])
    for key, (ok, issues) in checks.items():
        result['checks'][key] = {'status': 'PASS' if ok else 'BLOCKED', 'issues': issues}
    result['status'] = ('PASS_AUTOMATED_INTEGRITY_ONLY' if all(ok for ok, _ in checks.values())
                        else 'BLOCKED') if mode == 'validation' else 'EXPLORATION_NO_SCIENTIFIC_CERTIFICATION'
    result['limitations'] = ['A single isolated repeat is not independent reproduction.',
                             'A DOI lookup checks bibliographic metadata, not cited findings.',
                             'Claims bind only declared result slots; untagged prose still needs review.',
                             'Statistical validity, novelty and publication readiness require independent examination.']
    return result
