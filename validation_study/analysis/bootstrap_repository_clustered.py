from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / 'results' / 'prr_real_history_pilot.json'
OUT = ROOT / 'results' / 'repository_clustered_bootstrap.json'
SEED = 20260923
N_BOOT = 10000


def _event_metrics(case_result: dict, system: str) -> dict[str, float]:
    ev = case_result['events'][0]
    truth = {k: set(ev['truth'].get(k, [])) for k in ('claims', 'decisions', 'assertions')}
    pred = {k: set(ev['systems'][system]['updated'].get(k, [])) for k in ('claims', 'decisions', 'assertions')}
    universes = {
        'claims': truth['claims'] | set(ev['truth'].get('claims_unaffected', [])) | pred['claims'],
        'assertions': truth['assertions'] | pred['assertions'],
        'decisions': truth['decisions'] | pred['decisions'],
    }
    # For false-invalidation denominator, unaffected claims are explicitly available in the truth object.
    unaffected_claims = set(ev['truth'].get('claims_unaffected', []))
    unaffected_assertions = set()
    # Infer unaffected assertions conservatively from prediction/truth universe when case object was mapped with paired assertions.
    # This is only used for the pilot CI and is not a replacement for independent annotations.
    # If an assertion is predicted but not truth it is a false invalidation.
    tp_c = len(pred['claims'] & truth['claims']); fn_c = len(truth['claims'] - pred['claims']); fp_c = len(pred['claims'] - truth['claims'])
    tp_a = len(pred['assertions'] & truth['assertions']); fn_a = len(truth['assertions'] - pred['assertions']); fp_a = len(pred['assertions'] - truth['assertions'])
    exact = float(all(pred[k] == truth[k] for k in ('claims','decisions','assertions')))
    return {
        'exact_event': exact,
        'claim_recall_num': float(tp_c), 'claim_recall_den': float(tp_c + fn_c),
        'claim_precision_num': float(tp_c), 'claim_precision_den': float(tp_c + fp_c),
        'claim_false_invalidation_num': float(fp_c),
        'claim_false_invalidation_den': float(fp_c + len(unaffected_claims - pred['claims'])),
        'claim_escape_num': float(fn_c), 'claim_escape_den': float(tp_c + fn_c),
        'assertion_recall_num': float(tp_a), 'assertion_recall_den': float(tp_a + fn_a),
        'assertion_precision_num': float(tp_a), 'assertion_precision_den': float(tp_a + fp_a),
        'assertion_escape_num': float(fn_a), 'assertion_escape_den': float(tp_a + fn_a),
    }


def _aggregate(rows: list[dict[str, float]]) -> dict[str, float | None]:
    if not rows:
        return {}
    def ratio(nkey, dkey):
        n=sum(r[nkey] for r in rows); d=sum(r[dkey] for r in rows)
        return None if d == 0 else n/d
    return {
      'exact_event_rate': sum(r['exact_event'] for r in rows)/len(rows),
      'claim_recall': ratio('claim_recall_num','claim_recall_den'),
      'claim_precision': ratio('claim_precision_num','claim_precision_den'),
      'claim_false_invalidation_rate': ratio('claim_false_invalidation_num','claim_false_invalidation_den'),
      'claim_escape_rate': ratio('claim_escape_num','claim_escape_den'),
      'assertion_recall': ratio('assertion_recall_num','assertion_recall_den'),
      'assertion_precision': ratio('assertion_precision_num','assertion_precision_den'),
      'assertion_escape_rate': ratio('assertion_escape_num','assertion_escape_den'),
    }


def ci(values: list[float]) -> dict[str, float]:
    a=np.asarray(values,float)
    return {'median':float(np.median(a)), 'lo95':float(np.quantile(a,0.025)), 'hi95':float(np.quantile(a,0.975))}


def main():
    data=json.load(open(IN))
    cases=data['cases']
    systems=list(data['summary'])
    by_repo=defaultdict(list)
    for c in cases:
        by_repo[c['source']['repository']].append(c)
    repos=sorted(by_repo)

    point={}
    for s in systems:
        rows=[_event_metrics(c,s) for c in cases]
        point[s]=_aggregate(rows)

    rng=np.random.default_rng(SEED)
    draws={s:defaultdict(list) for s in systems}
    paired=defaultdict(list)
    for _ in range(N_BOOT):
        sampled=list(rng.choice(repos,size=len(repos),replace=True))
        sample_cases=[]
        for repo in sampled:
            sample_cases.extend(by_repo[repo])
        metrics={}
        for s in systems:
            metrics[s]=_aggregate([_event_metrics(c,s) for c in sample_cases])
            for k,v in metrics[s].items():
                if v is not None: draws[s][k].append(v)
        # Pre-specified paired contrasts for the mechanism claim.
        paired['trl_minus_binary_claim_recall'].append(metrics['trl_v14']['claim_recall']-metrics['binary_edges']['claim_recall'])
        paired['trl_minus_binary_claim_escape'].append(metrics['trl_v14']['claim_escape_rate']-metrics['binary_edges']['claim_escape_rate'])
        a=metrics['trl_v14']['claim_false_invalidation_rate']; b=metrics['downstream_reachability']['claim_false_invalidation_rate']
        if a is not None and b is not None:
            paired['trl_minus_reachability_false_invalidation'].append(a-b)
        paired['trl_minus_supportset_exact'].append(metrics['trl_v14']['exact_event_rate']-metrics['support_set_provenance']['exact_event_rate'])

    out={
      'schema':'prr-repository-clustered-bootstrap-1',
      'scope':'Repository-clustered bootstrap over the 10-event authored real-history structural pilot. These intervals quantify pilot sampling variability only; they are not external-validation intervals because dependency gold was authored for the pilot.',
      'seed':SEED,'bootstrap_replicates':N_BOOT,'repositories':repos,'n_repositories':len(repos),'n_events':len(cases),
      'point_estimates':point,
      'confidence_intervals':{s:{k:ci(v) for k,v in m.items()} for s,m in draws.items()},
      'paired_contrasts':{k:ci(v) for k,v in paired.items()},
    }
    OUT.write_text(json.dumps(out,indent=2)+'\n')
    print(OUT)
    for s in systems:
        print(s, point[s])
    print('paired')
    for k,v in out['paired_contrasts'].items(): print(k,v)

if __name__=='__main__': main()
