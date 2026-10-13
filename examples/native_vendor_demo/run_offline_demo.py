"""Reproducible, deliberately SCRIPTED demonstration of two native vendor engines.

This script runs the actual Factory scientific idea gate, native Referee Lean v2
(review/diff) engine and V5 schema/semantic checker. No research model is called.
Scores and Referee fixture findings are authored test inputs, not AI discovery.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from factory.steps import idea
from factory.integrations import idea_discovery, referee_native

HERE = Path(__file__).resolve().parent
TOPIC = "Detecting evaluation leakage in brain-tumor MRI segmentation studies"

CANDIDATES = [
    {"id":"MRI-01", "title":"Multi-level leakage stress test for brain MRI segmentation",
     "hypothesis":"Compared with random-slice splitting, patient- and acquisition-site-disjoint evaluation yields a mean Dice decrease exceeding 0.03 on sufficiently heterogeneous, legitimately obtained datasets; a preregistered study would test this prediction.",
     "method":"On licensed multi-site segmentation data, compare random-slice, patient-disjoint and site-holdout splits with the same architecture and fixed tuning budget. Report bootstrapped site-cluster intervals and repeat seeds.",
     "falsifier":{"statement":"Reject the preregistered overoptimism hypothesis if the paired mean Dice gap is at most 0.03.","metric":"paired_mean_dice_gap_random_slice_minus_site_holdout","threshold":0.03}},
    {"id":"MRI-02","title":"Calibrated abstention for domain-shift segmentation",
     "hypothesis":"An uncertainty-based abstention rule trained only on the training cohort improves out-of-domain poor-case detection AUROC by more than 0.02 compared with entropy alone.",
     "method":"Train a shared segmentation backbone, predeclare AUROC comparison and risk-coverage curves, assess held-out institutions.",
     "falsifier":{"statement":"Reject the predictive improvement if the held-out poor-case detection AUROC gain is 0.02 or less.","metric":"auroc_gain_abstention_vs_entropy","threshold":0.02}},
    {"id":"MRI-03","title":"Worst-site threshold tuning under imaging shift",
     "hypothesis":"Training-only minimax calibration improves worst-site lesion-level sensitivity by more than 0.01 without materially increasing false-positive burden.",
     "method":"Use registered multi-site data splits and a frozen lesion-level detection benchmark with explicit false-positive limits.",
     "falsifier":{"statement":"Reject the improvement if worst-site lesion sensitivity increases by at most 0.01.","metric":"worst_site_sensitivity_gain","threshold":0.01}},
]

# Deterministic scripted mock returns. The native Factory idea selection and
# falsifier/ranking functions *are* executed; generation/model scoring is not.
SCORES = {
 'novelty-skeptic': {
    'MRI-01':(7,9,8,9,7), 'MRI-02':(5,8,7,9,6), 'MRI-03':(4,7,6,8,5)},
 'methods-realist': {
    'MRI-01':(6,9,7,9,8), 'MRI-02':(6,8,7,8,7), 'MRI-03':(5,7,6,8,6)},
}

class ScriptedIdeaAgent:
    calls=0
    def run(self, prompt, checker, schema_path=None):
        self.__class__.calls += 1
        if self.calls == 1:
            payload={'ideas':CANDIDATES}
        else:
            persona = ('novelty-skeptic' if self.calls == 2 else 'methods-realist')
            payload={'reviews':[{'idea_id': candidate['id'], **dict(zip(idea.SCORE_FIELDS,SCORES[persona][candidate['id']]))}
                                for candidate in CANDIDATES]}
        errors=checker(payload)
        if errors:
            raise ValueError('scripted demonstration violates Factory validator: ' + str(errors))
        return {'payload':payload}


def run_demo(workspace):
    workspace=Path(workspace).resolve()
    workspace.mkdir(parents=True,exist_ok=True)
    (workspace/'_inputs').mkdir(exist_ok=True)
    (workspace/'_inputs'/'topic.md').write_text(TOPIC+'\n',encoding='utf-8')
    ScriptedIdeaAgent.calls=0
    results=idea.generate(TOPIC,agent_factory=ScriptedIdeaAgent)
    (workspace/'_inputs'/'ideas.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    selected=idea.select(workspace,workspace/'_inputs'/'ideas.json')
    (workspace/'1_idea'/'ideas.generated.SCRIPTED_DEMO.json').write_text(json.dumps(results,indent=2)+'\n')
    winner=next(item for item in results['ideas'] if item['id']==selected['winner'])
    raw_idea={'ideas':[{
      'idea_id':winner['id'], 'source_gap':'G-MRI-001','title':winner['title'],
      'hypothesis':{'statement':winner['hypothesis'], 'null_hypothesis':'No preregistered improvement or degradation beyond the threshold'},
      'method_sketch':{'steps':winner['method']},
      'experiment_design':{'falsifier':winner['falsifier'], 'status':'NOT_EXECUTED'},
      'expected_outcomes':{'if_negative':'Reject or narrow the hypothesis and document the negative result without altering the preregistration.'},
      'scoring':{'kind':'SCRIPTED_DEMONSTRATION_ONLY'},
    }], 'traceability_matrix':[{'gap_id':'G-MRI-001', 'source':'PROPOSED_NOT_VERIFIED'}]}
    prepared=idea_discovery.prepare(workspace)
    sys.path.insert(0,str(Path(prepared['path'])/'scripts'))
    from schema_validator import validate_json,validate_semantics
    schema=Path(prepared['path'])/'schemas'/'idea_report.schema.json'
    errors=validate_json(raw_idea,schema,raise_on_error=False)+validate_semantics('idea_report',raw_idea)
    (workspace/'1_idea'/'v5_idea_report.json').write_text(json.dumps(raw_idea,indent=2)+'\n')
    if errors:
        raise ValueError('Vendor V5 idea schema/semantic errors: '+str(errors))
    drafts=[HERE/x for x in ('v1_original.md','v2_reframed.md','v3_limited.md')]
    fixtures=[HERE/f'scripted_round_{i}.json' for i in (1,2,3)]
    outcome=referee_native.iterate(workspace,drafts,provider='scripted',scripted_responses=fixtures,
                                   mode='standard',search_backend='scripted',timeout=120)
    if outcome['major_concerns_by_round']!=[1,1,0]:
        raise ValueError('Unexpected Referee regression: '+str(outcome))
    description={
       'status':'OFFLINE_INTEGRATION_SMOKE_PASSED', 'scientific_novelty_verified':False,
       'human_scientific_review_completed':False, 'live_llm_invoked':False,
       'experiment_executed':False, 'sample_topic':TOPIC,
       'selected_idea':winner['id'], 'idea_aggregate_score':selected['ideas'][0]['aggregate_score'],
       'idea_scoring':'SCRIPTED_PERSONAS_NOT_EVALUATED_SCIENTIFICALLY',
       'v5_schema_validation':'PASS', 'v5_pipeline_execution':'NOT_EXECUTED',
       'referee_review_engine':'REAL_VENDOR_ENGINE_WITH_SCRIPTED_MODEL_RESPONSES',
       'manuscript_revision_mode':'PREPARED_EXAMPLE_DRAFTS, NOT AUTONOMOUS EDITING',
       'major_concerns_by_round':outcome['major_concerns_by_round'],
       'idea_selection':str(workspace/'1_idea'/'tournament.json'),
       'native_review_history':outcome['report_path'],
    }
    (workspace/'demo_results.json').write_text(json.dumps(description,indent=2)+'\n')
    return description

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--workspace',default=str(ROOT/'examples'/'native_vendor_demo'/'runtime_smoke'))
    args=p.parse_args()
    print(json.dumps(run_demo(args.workspace),indent=2))
