"""Author-rubric + V5 science gate + native Beihang integration regression.

Tests are offline; the one real engine invocation uses a scripted model fixture.
"""
from pathlib import Path
from unittest.mock import patch
import json
import tempfile
import unittest

from factory.config import validate_context
from factory.integrations import referee_beihang, idea_discovery
from factory.steps import review

class BeihangUpgradeTests(unittest.TestCase):
    def test_native_core_and_trusted_user_rubric_run_with_offline_fixture(self):
        with tempfile.TemporaryDirectory() as workspace:
            paper=referee_beihang.VENDOR/'examples/demo_manuscript.md'
            responses=referee_beihang.VENDOR/'examples/demo_responses.json'
            result=referee_beihang.review_one(workspace,paper,provider='scripted',
                fixtures=[responses], mode='standard',search_backend='none')
            self.assertEqual(result['engine'],'beihang-referee-0.1.0')
            self.assertTrue(result['review_exportable'])
            self.assertEqual(result['admitted_major_concerns'],1)
            self.assertTrue(result['scripted_test_only'])
            config=json.loads((Path(result['run_directory'])/'config.json').read_text())
            self.assertEqual(config['extra']['trusted_rubric_sha256'],
                json.loads((Path(workspace)/'beihang_referee'/
                    f'review_cycle_{referee_beihang._sha(paper)[:16]}.json').read_text())['trusted_additional_rubric_sha256'])
            self.assertIn('Construct Clarity',config['extra']['trusted_additional_rubric'])

    def test_invalid_beihang_options_are_rejected(self):
        for ctx in ({'referee_pipeline':'legacy'}, {'referee_mode':'x'},
                    {'referee_scorecard':'yes'}, {'referee_search_backend':'wrong'}):
            with self.assertRaises(ValueError):
                validate_context(ctx)

    def test_credentials_required_and_not_fabricated(self):
        with tempfile.TemporaryDirectory() as workspace:
            paper=referee_beihang.VENDOR/'examples/demo_manuscript.md'
            with patch.dict('os.environ',{'OPENAI_API_KEY':'','REFEREE_MODEL':''}):
                with self.assertRaisesRegex(ValueError,'OPENAI_API_KEY'):
                    referee_beihang.review_one(workspace,paper)
            with self.assertRaisesRegex(ValueError,'one declared JSON'):
                referee_beihang.review_one(workspace,paper,provider='scripted',fixtures=[])

    def test_no_same_manuscript_multiround_replay(self):
        with tempfile.TemporaryDirectory() as workspace:
            paper=referee_beihang.VENDOR/'examples/demo_manuscript.md'
            fixture=referee_beihang.VENDOR/'examples/demo_responses.json'
            with self.assertRaisesRegex(ValueError,'materially distinct'):
                referee_beihang.review_cycle(workspace,[paper,paper],provider='scripted',
                    fixtures=[fixture,fixture])

    def test_validates_new_beihang_factory_backend(self):
        self.assertEqual(validate_context({'review_agent':'beihang-native'})['review_agent'],
                         'beihang-native')

    def test_factory_revises_then_invokes_beihang_with_prior_concerns(self):
        with tempfile.TemporaryDirectory() as workspace:
            root=Path(workspace)
            source=root/'2_paper';(source/'build').mkdir(parents=True)
            before=r'\documentclass{article}\begin{document}Causal effect.\end{document}'
            after=r'\documentclass{article}\begin{document}Descriptive difference.\end{document}'
            (source/'paper.tex').write_text(before)
            (source/'paper.pdf').write_bytes(b'first synthetic pdf stub')
            (source/'build'/'paper.tex').write_text(before)
            runs=[]
            for i,counts in enumerate((1,0)):
                d=root/f'review_{i}';d.mkdir()
                (d/'state.json').write_text(json.dumps({'admitted_concerns':[
                    {'title':'Causal mechanism', 'failure_mechanism':'No comparison group',
                     'minimum_resolution':'Limit claims to association'}]*counts,'rejected_concerns':[]}))
                (d/'review.md').write_text('Test report; synthetic only')
                (d/'prior.json').write_text('[]')
                runs.append({'run_directory':str(d),'review_markdown':str(d/'review.md'),
                    'review_exportable':True,'hard_invariant_failures':0,
                    'prior_concerns':str(d/'prior.json'),
                    'revision_closure':None if i==0 else {'closure_rows':[],
                    'new_regressions':[],'summary':{'status':'test'}}})
            class Editor:
                def run(self,prompt,validator,schema_path=None):
                    payload={'paper_tex':after,'changes':['narrow causal claim']}
                    assert validator(payload)==[]
                    return {'payload':payload}
            def fake_build(directory, filename):
                pdf=Path(directory)/'paper.pdf';pdf.write_bytes(b'changed test PDF');return pdf
            with patch.object(referee_beihang,'review_one',side_effect=runs) as engine:
                result=review.run(root,{'review_agent':'beihang-native','review_max_rounds':3},
                    revise=True,agent_factory=lambda *_:Editor(),build=fake_build)
            self.assertEqual(engine.call_count,2)
            second=engine.call_args_list[1]
            self.assertIsNotNone(second.kwargs['prior_manuscript'])
            self.assertIsNotNone(second.kwargs['prior_concerns'])
            self.assertEqual(result['review_backend'],'beihang-native')
            self.assertIn('Descriptive difference',(root/'3_review'/'final'/'paper.tex').read_text())

    def test_v5_phase10_to16_evidence_audit_not_claimed_as_empirical(self):
        with tempfile.TemporaryDirectory() as workspace:
            root=Path(workspace)
            source=root/'_vendor'/'idea-discovery-v5'/'output'
            missing=idea_discovery.phase_audit(root,idea_id='IDEA-001')
            self.assertEqual(missing['status'],'INCOMPLETE')
            expected={10:'phase10_scorecard.json',11:'phase11_novelty_attack.json',
                      12:'phase12_novelty_matrix.json',13:'phase13_reviewer_attack.json',
                      14:'phase14_revision_or_kill.json',15:'phase15_hypothesis_contract.json',
                      16:'phase16_occam_counterexample.json'}
            for phase,filename in expected.items():
                section='attack_loop' if phase<=14 else 'falsification'
                out=source/section/'IDEA-001'/'round_01';out.mkdir(parents=True,exist_ok=True)
                (out/filename).write_text(json.dumps({'synthetic_test_only':True,'status':'fixture'}))
            result=idea_discovery.phase_audit(root,idea_id='IDEA-001')
            self.assertEqual(result['status'],'ARTIFACTS_RECORDED_NOT_SCIENTIFICALLY_VERIFIED')
            self.assertEqual([x['phase'] for x in result['phases']],list(range(10,17)))
            self.assertIn('does not establish novelty',result['caveat'])
            self.assertTrue(result['phases'][0]['rounds'][0]['sha256'])

if __name__=='__main__':unittest.main()
