import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))

from step7c_falsification import (
    validate_contract, validate_mve_evidence, final_decision_from_evidence,
    _blind_payload, run_falsification,
)
from step7b_survivor_elo import greenlight_survivors


def idea():
    return {
        'idea_id':'I1','title':'Mechanism study','source_gap':'G1','gap_type':'VOID',
        'hypothesis':{'statement':'X causes Y under Z','null_hypothesis':'X does not change Y'},
        'method_sketch':{'approach':'controlled test','key_components':['X'],'baselines':['B'],'ablations':['remove X']},
        'experiment_design':{'datasets':['D'],'metrics':['M'],'minimum_viable_experiment':'small controlled pilot'},
        'feasibility':{'compute_estimate':'small'}
    }


def contract():
    return {
        'idea_id':'I1','central_hypothesis':'X causes Y under Z','null_hypothesis':'X does not change Y',
        'mechanism_claim':'X changes Y through M',
        'observable_predictions':[{'prediction':'Y rises','measure':'M','direction':'increase','decision_threshold':'>0'}],
        'supporting_evidence_would_be':['controlled increase'],
        'weakening_evidence_would_be':['unstable effect'],
        'falsifying_evidence_would_be':['no effect under controlled test'],
        'competing_explanations':['C'],'confounders':['Q'],'boundary_conditions':['Z'],
        'minimal_decisive_experiment':'controlled pilot','contract_quality':'PASS','contract_issues':[]
    }


def occam(verdict='PASS'):
    return {'idea_id':'I1','occam_tests':[],'counterexample_tests':[],'negative_controls':['N'],
            'positive_controls':['P'],'competing_explanation_tests':['C'],'leakage_or_shortcut_tests':['L'],
            'cheapest_high_information_test':'T','complexity_justified':'YES','fatal_design_issue':'','verdict':verdict}


def mve():
    return {'idea_id':'I1','objective':'falsify X->Y','primary_claim_under_test':'X causes Y','dataset_or_material':'D',
            'sampling_or_subset':'subset','strongest_baselines':['B'],'controls':['N','P'],'critical_ablation':'remove X',
            'primary_metric':'M','secondary_metrics':[],'minimum_repeats_or_seeds':'3','success_rule':'effect > threshold',
            'falsification_rule':'no effect','inconclusive_rule':'wide uncertainty','leakage_checks':['L'],
            'artifacts_required':['raw results'],'estimated_cost':'small','execution_command':'','notes':'manual'}


def blind(verdict='PASS'):
    return {'idea_id':'I1','testability':'PASS','mechanism_identifiability':'PASS','confounding_control':'PASS',
            'counterexample_strength':'PASS','occam_status':'PASS','minimal_experiment_is_decisive':True,
            'unresolved_threats':[],'required_changes':[],'verdict':verdict,'reason':'ok'}


class V5ValidationTests(unittest.TestCase):
    def test_contract_requires_falsifiers(self):
        x=contract(); x['falsifying_evidence_would_be']=[]
        self.assertTrue(any('falsifying' in e for e in validate_contract(x)))

    def test_evidence_validation_requires_execution_and_artifacts(self):
        errs=validate_mve_evidence({'idea_id':'I1','executed':False,'results':{},'artifacts':[]},'I1')
        self.assertGreaterEqual(len(errs),3)

    def test_final_greenlight_requires_strong_controlled_support(self):
        a={'verdict':'SUPPORTED','evidence_quality':'MEDIUM','protocol_adherence':'FULL','negative_controls_passed':True,'leakage_checks_passed':True,'supports_hypothesis':True,'supports_mechanism':True}
        l={'overall_status':'SUPPORTED','full_study_justified':True}
        self.assertEqual(final_decision_from_evidence(a,l),'GREENLIGHT')
        a['verdict']='INCONCLUSIVE'
        self.assertEqual(final_decision_from_evidence(a,l),'REVISE_EVIDENCE')

    def test_blind_payload_excludes_generator_score_and_rationale(self):
        p=_blind_payload(contract(),occam(),mve())
        self.assertEqual(set(p),{'hypothesis_contract','falsification_plan','mve_protocol'})
        self.assertNotIn('scorecard',json.dumps(p))
        self.assertNotIn('generator_rationale',json.dumps(p))

    def test_ready_for_mve_is_not_elo_survivor(self):
        summary={'ideas':[{'final_decision':'READY_FOR_MVE','final_idea':idea(),'mve_evidence_present':False},
                          {'final_decision':'GREENLIGHT','final_idea':dict(idea(),idea_id='I2'),'mve_evidence_present':True}]}
        self.assertEqual([x['idea_id'] for x in greenlight_survivors(summary)],['I2'])


class V5StageTests(unittest.TestCase):
    def _base(self,td):
        out=Path(td)
        (out/'attack_loop_summary.json').write_text(json.dumps({'ideas':[{'idea_id':'I1','final_decision':'GREENLIGHT','rounds_run':2,'final_idea':idea()}]}),encoding='utf-8')
        return {'pipeline':{'output_dir':td},'falsification':{'enabled':True,'max_rounds':2},'attack_loop':{'max_rounds':2},'citation_expansion':{'enabled':False}}

    def test_no_real_evidence_stops_at_ready_for_mve(self):
        class Author:
            def __init__(self,config=None): self.n=0
            def ask_json(self,system,user,temperature=0.0):
                self.n+=1; return contract() if self.n==1 else mve()
        class Verifier:
            actual_provider='independent-test'
            def __init__(self,config): self.n=0
            def ask_json(self,system,user,temperature=0.0):
                self.n+=1; return occam() if self.n==1 else blind()
        with tempfile.TemporaryDirectory() as td:
            cfg=self._base(td)
            with patch('step7c_falsification.ClaudeClient',Author), patch('step7c_falsification.AttackClient',Verifier):
                r=run_falsification(cfg)
            self.assertEqual(r['ideas'][0]['final_decision'],'READY_FOR_MVE')
            self.assertFalse(r['ideas'][0]['mve_evidence_present'])

    def test_real_supported_evidence_can_greenlight(self):
        class Author:
            def __init__(self,config=None): self.n=0
            def ask_json(self,system,user,temperature=0.0):
                self.n+=1; return contract() if self.n==1 else mve()
        class Verifier:
            actual_provider='independent-test'
            def __init__(self,config): self.n=0
            def ask_json(self,system,user,temperature=0.0):
                self.n+=1
                if self.n==1: return occam()
                if self.n==2: return blind()
                if self.n==3: return {'idea_id':'I1','evidence_quality':'HIGH','protocol_adherence':'FULL','primary_result':'positive controlled effect','effect_and_uncertainty':'CI excludes null','supports_hypothesis':True,'supports_mechanism':True,'rules_out_key_alternatives':True,'negative_controls_passed':True,'leakage_checks_passed':True,'replication_strength':'3 seeds','contradictions':[],'limitations':[],'verdict':'SUPPORTED','reason':'controlled evidence'}
                return {'idea_id':'I1','claims':[{'claim':'X causes Y','supporting_evidence':['MVE'],'contradicting_evidence':[],'missing_evidence':['external replication'],'status':'SUPPORTED'}],'overall_status':'SUPPORTED','remaining_alternatives':[],'full_study_justified':True,'reason':'pilot supports larger study'}
        with tempfile.TemporaryDirectory() as td:
            cfg=self._base(td); evdir=Path(td)/'mve_evidence'; evdir.mkdir()
            (evdir/'I1.json').write_text(json.dumps({'idea_id':'I1','executed':True,'results':{'effect':1.2},'artifacts':['results.csv'],'controls':{'negative':'pass'},'leakage_checks':{'status':'pass'}}),encoding='utf-8')
            with patch('step7c_falsification.ClaudeClient',Author), patch('step7c_falsification.AttackClient',Verifier):
                r=run_falsification(cfg)
            self.assertEqual(r['ideas'][0]['final_decision'],'GREENLIGHT')
            self.assertTrue(r['ideas'][0]['mve_evidence_present'])

    def test_falsification_revision_forces_phase10_restart(self):
        revised=dict(idea(),title='Revised mechanism')
        class Author:
            def __init__(self,config=None): self.n=0
            def ask_json(self,system,user,temperature=0.0):
                self.n+=1
                if self.n==1: return contract()
                if self.n==2: return mve()
                return {'decision':'REVISE','reason':'fix confounder','revised_idea':revised,'changes':[{'blocker':'confounder','scientific_change':'new control'}],'requires_new_literature_attack':True}
        class Verifier:
            actual_provider='independent-test'
            def __init__(self,config): self.n=0
            def ask_json(self,system,user,temperature=0.0):
                self.n+=1
                return occam('REVISE') if self.n==1 else blind('REVISE')
        with tempfile.TemporaryDirectory() as td:
            cfg=self._base(td)
            with patch('step7c_falsification.ClaudeClient',Author), patch('step7c_falsification.AttackClient',Verifier), \
                 patch('step7c_falsification.rerun_literature_survival',return_value=('KILL',revised,[])) as reattack:
                r=run_falsification(cfg)
            self.assertTrue(reattack.called)
            self.assertEqual(r['ideas'][0]['final_decision'],'KILL')

if __name__=='__main__': unittest.main()
