"""Regression tests for the *actual* bundled vendor interfaces; no API calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from factory.config import validate_context
from factory.integrations import idea_discovery, referee_native
from factory.pipeline.stages import artifact_valid
from factory.steps import idea, review

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'examples' / 'native_vendor_demo'


class NativeVendorIntegrationTests(unittest.TestCase):
    def test_native_referee_engine_offline_three_rounds(self):
        with tempfile.TemporaryDirectory() as folder:
            draft = [DEMO / x for x in ('v1_original.md', 'v2_reframed.md', 'v3_limited.md')]
            fixtures = [DEMO / f'scripted_round_{k}.json' for k in (1,2,3)]
            report = referee_native.iterate(folder, draft,
                provider='scripted', scripted_responses=fixtures,
                mode='standard', search_backend='scripted', timeout=60)
            self.assertEqual(report['major_concerns_by_round'], [1, 1, 0])
            self.assertTrue(report['scripted_test_only'])
            saved = json.loads(Path(report['report_path']).read_text())
            self.assertEqual(len(saved['rounds']), 3)
            self.assertFalse(saved['automatic_manuscript_revision'])
            for row in saved['rounds']:
                self.assertTrue(row['assessment']['review_exportable'])
                self.assertEqual(row['assessment']['hard_invariant_failures'], 0)
                self.assertTrue(Path(row['assessment']['review_markdown']).is_file())

    def test_model_is_required_for_native_review(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict('os.environ', {'REFEREE_MODEL': '', 'OPENAI_API_KEY': ''}):
                with self.assertRaisesRegex(ValueError, 'model is required'):
                    referee_native.review(folder, DEMO / 'v1_original.md')

    def test_empty_scripted_responses_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'explicit fixture'):
                referee_native.review(folder, DEMO / 'v1_original.md', provider='scripted')

    def test_factory_native_first_pass_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paper = root / '2_paper'
            paper.mkdir()
            (paper / 'paper.tex').write_text('\\documentclass{article}\\begin{document}Test\\end{document}')
            (paper / 'paper.pdf').write_bytes(b'PDF mock only; no vendor review is invoked')
            external = root / 'scripted_vendor'
            external.mkdir()
            (external / 'review.md').write_text('Sample anchored reviewer note.')
            (external / 'state.json').write_text(json.dumps({'admitted_concerns': [
                {'title': 'Causal identification', 'failure_mechanism': 'No control',
                 'minimum_resolution': 'Limit causal wording'}],
                 'rejected_concerns': []}))
            with patch.object(referee_native, 'review', return_value={
                    'review_exportable': True, 'hard_invariant_failures': 0,
                    'run_directory': str(external), 'review_markdown': str(external / 'review.md')}):
                payload = review.run(root, {'review_agent': 'referee-native'}, revise=False)
            self.assertEqual(payload['final_admitted_major_concerns'], 1)
            self.assertEqual(payload['status'], 'NATIVE_SINGLE_PASS')
            ok, _ = artifact_valid(root, 'S3')
            self.assertTrue(ok)

    def test_factory_native_guarded_revision_and_rereview(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / '5_refine' / 'source'
            (source / 'build').mkdir(parents=True)
            original = r"\documentclass{article}\begin{document}This is causal.\end{document}"
            revised = r"\documentclass{article}\begin{document}This is descriptive.\end{document}"
            (source / 'paper.tex').write_text(original)
            (source / 'paper.pdf').write_bytes(b'example one')
            (source / 'build' / 'paper.tex').write_text(original)
            stage_runs = []
            for i, names in enumerate((['Causal language'], [])):
                run_dir = root / f'scripted_round_{i}'
                run_dir.mkdir()
                (run_dir / 'state.json').write_text(json.dumps({'admitted_concerns': [
                    {'title': name, 'failure_mechanism':'No concurrent group',
                     'minimum_resolution':'Use descriptive wording'} for name in names],
                     'rejected_concerns': []}))
                (run_dir / 'review.md').write_text('Anchored narrative review for testing.')
                stage_runs.append({'run_directory':str(run_dir), 'review_markdown':str(run_dir/'review.md'),
                                   'review_exportable':True, 'hard_invariant_failures':0})
            class Editor:
                def run(self, prompt, validator, schema_path=None):
                    payload={'paper_tex':revised,'changes':['Removed causal claim']}
                    assert validator(payload) == []
                    return {'payload':payload}
            def fake_build(directory, filename):
                p=Path(directory) / 'paper.pdf'
                p.write_bytes(b'example revision two')
                return p
            with patch.object(referee_native, 'review', side_effect=stage_runs) as reviewed:
                result=review.run(root, {'review_agent':'referee-native','review_max_rounds':3},
                                  source_dir=source, out_name='5_refine',revise=True,
                                  agent_factory=lambda *_args:Editor(), build=fake_build)
            self.assertEqual(reviewed.call_count, 2)
            self.assertEqual(result['status'],'NATIVE_NO_ADMITTED_MAJOR_CONCERNS')
            self.assertEqual(result['final_admitted_major_concerns'],0)
            self.assertIn('descriptive', (root/'5_refine'/'final'/'paper.tex').read_text())
            self.assertTrue(artifact_valid(root,'S5')[0])

    def test_factory_native_final_artifact_requires_zero_concerns(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / '5_refine'
            root.mkdir()
            summary = {'schema_version': 1, 'status': 'NATIVE_NO_ADMITTED_MAJOR_CONCERNS',
                       'review_backend': 'referee-native', 'final_scores': {},
                       'final_admitted_major_concerns': 0, 'rounds': [{'round': 1}]}
            (root / 'report.json').write_text(json.dumps(summary))
            ok, _ = artifact_valid(folder, 'S5')
            self.assertTrue(ok)
            summary['status'] = 'NATIVE_MAX_ROUNDS'
            (root / 'report.json').write_text(json.dumps(summary))
            ok, _ = artifact_valid(folder, 'S5')
            self.assertFalse(ok)

    def test_v5_safe_run_requires_sources_and_real_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '_inputs').mkdir()
            (root / '_inputs' / 'topic.md').write_text('Leakage-resistant brain MRI evaluation')
            doc = root / 'source_paper.md'
            doc.write_text('# illustrative paper\n## Methods\nExample only.')
            demo = idea_discovery.run(root, papers=[doc], dry_run=True)
            self.assertEqual(demo['status'], 'DRY_RUN')
            self.assertTrue(demo['no_auto_execution_of_proposed_experiments'])
            with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}):
                with self.assertRaisesRegex(ValueError, '(ANTHROPIC_API_KEY|requires anthropic)'):
                    idea_discovery.run(root, papers=[doc], dry_run=False)

    def test_v5_adoption_explicit_reproducible_and_tamper_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '_inputs').mkdir()
            prepared = idea_discovery.prepare(root)
            output = Path(prepared['path']) / 'output'
            outcome = {
                'ideas': [{'idea_id':'IDEA-001','final_decision':'READY_FOR_MVE',
                           'mve_evidence_present':False,
                           'final_idea': {
                               'title':'Testable MRI research idea',
                               'hypothesis':{'statement':'Patient holdout generalization differs from slice split.'},
                               'method_sketch': {'approach': 'Comparable held-out test sets'}}}]}
            (output/'falsification_summary.json').write_text(json.dumps(outcome))
            adopted = idea_discovery.adopt(root, idea_id='IDEA-001', metric='mean_dice_gap',
                          threshold=0.03,
                          falsifier_statement='Reject if measured mean Dice gap is below 0.03.',
                          operator_acknowledgement=True)
            self.assertEqual(adopted['v5_decision'],'READY_FOR_MVE')
            selected = idea.run(root)
            self.assertEqual(selected['winner'],'IDEA-001')
            self.assertIsNone(selected['aggregate_score'])
            self.assertTrue((root/'1_idea'/'idea.md').is_file())
            self.assertTrue(artifact_valid(root,'S1')[0])
            outcome['ideas'][0]['final_idea']['title']='Altered after approval'
            (output/'falsification_summary.json').write_text(json.dumps(outcome))
            with self.assertRaisesRegex(ValueError,'source changed'):
                idea.run(root)

    def test_native_empty_proposals_with_rejected_major_does_not_certify(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'2_paper').mkdir()
            (root/'2_paper'/'paper.tex').write_text('\\begin{document}draft\\end{document}')
            (root/'2_paper'/'paper.pdf').write_bytes(b'pdf fixture')
            out = root/'vendorrun'
            out.mkdir()
            (out/'review.md').write_text('Rejected candidate gate review.')
            (out/'state.json').write_text(json.dumps({'admitted_concerns': [],
                       'rejected_concerns':[{'title':'Unanchored claim'}]}))
            fake={'review_exportable':True,'hard_invariant_failures':0,
                  'run_directory':str(out),'review_markdown':str(out/'review.md')}
            with patch.object(referee_native,'review',return_value=fake):
                result = review.run(root, {'review_agent':'referee-native'}, revise=False)
            self.assertNotEqual(result['status'],'NATIVE_NO_ADMITTED_MAJOR_CONCERNS')

    def test_review_context_native_is_opt_in(self):
        self.assertEqual(validate_context({'review_agent': 'referee-native'})['review_agent'], 'referee-native')
        with self.assertRaises(ValueError):
            validate_context({'review_agent': 'unknown'})


if __name__ == '__main__':
    unittest.main()
