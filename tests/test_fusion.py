"""Regression coverage for cross-project scientific provenance integration."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factory.config import validate_context
from factory.integrations.ledger import (
    record_idea, import_docker_run, verify_run_receipt, ledger_report,
)
from factory.integrations.methodology import brief
from researchledger.models import load_claims, load_evidence
from researchledger.reproduce import reproduce
from researchledger.validator import validate
from researchledger.workspace import Workspace


class FusionTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix='pf-fusion-'))
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        for d in ('1_idea', '2_paper', '4_code'):
            (self.project / d).mkdir()
        (self.project / '1_idea' / 'idea.md').write_text(
            '# Pilot hypothesis\n\n## Hypothesis\n\nChange X improves Y compared to Z.\n')
        (self.project / '2_paper' / 'results_spec.json').write_text(json.dumps({
            'slots': [{'id': 'accuracy', 'kind': 'value', 'describe': 'pilot accuracy'}]}))
        repo = self.project / '4_code' / 'repo'
        repo.mkdir()
        (repo / 'pf_run.py').write_text('# simulated test fixture; not executed here\n')
        from factory.steps.code import tree_hash
        self.repo_hash = tree_hash(repo)
        self.results_path = self.project / '4_code' / 'results.json'
        self.good_results = {
            'schema_version': 1, 'values': {'accuracy': 0.8}, 'series': {},
            'notes': 'Synthetic pilot, no clinical claims', 'scale': 'pilot',
            'image': 'python:3.11-slim', 'repo_sha256': self.repo_hash,
            'command': ['python', 'pf_run.py'], 'attempts': [
                {'attempt': 1, 'install': 'PASS', 'run': 'PASS', 'returncode': 0,
                 'problems': []}],
        }
        self.results_path.write_text(json.dumps(self.good_results))
        for name in ('experimental_log.generated.md', 'unresolved.json'):
            (self.project / '4_code' / name).write_text('[]' if name.endswith('.json') else 'Synthetic pilot')

    def test_evidence_is_checked_not_verified_and_imports_once(self):
        idea = record_idea(self.project)
        receipt = import_docker_run(self.project)
        self.assertEqual(receipt['claim_ids'], [idea['claim_id']])
        self.assertEqual(import_docker_run(self.project), receipt)
        ws = Workspace(self.project)
        self.assertEqual(len(load_evidence(ws)), 1)
        self.assertEqual(len(list(ws.runs_dir.iterdir())), 1)
        ev = list(load_evidence(ws).values())[0]
        self.assertEqual(ev.status, 'checked')
        self.assertEqual(load_claims(ws)[idea['claim_id']].status, 'provisional')
        self.assertFalse(validate(ws).errors)
        self.assertTrue(verify_run_receipt(self.project)[0])
        self.assertEqual(ledger_report(self.project)['independent_reproduction_status'], 'NOT_AUTOMATICALLY_ASSESSED')

    def test_new_docker_execution_earns_new_run_id_even_with_same_metrics(self):
        import_docker_run(self.project)
        from factory.integrations.ledger import import_docker_run as import_again
        original = json.loads((self.project / 'control' / 'ledger_s4_receipt.json').read_text())
        second = import_again(self.project, force_new=True)
        self.assertNotEqual(original['run_id'], second['run_id'])
        self.assertTrue(verify_run_receipt(self.project)[0])
        self.assertEqual(len(list(Workspace(self.project).runs_dir.iterdir())), 2)

    def test_methodology_reaches_peer_review_prompt(self):
        from factory.steps.review import review_prompt
        self.assertIn('peer-review-panel', review_prompt('an extracted manuscript', methodology=brief('review')))

    def test_modified_results_block_refinement_gate(self):
        record_idea(self.project)
        import_docker_run(self.project)
        self.good_results['values']['accuracy'] = 0.95
        self.results_path.write_text(json.dumps(self.good_results))
        ok, detail = verify_run_receipt(self.project)
        self.assertFalse(ok)
        self.assertIn('hash mismatch', detail)

    def test_revised_generated_code_fails_gate_even_if_metrics_identical(self):
        import_docker_run(self.project)
        (self.project / '4_code' / 'repo' / 'pf_run.py').write_text('changed!')
        valid, reason = verify_run_receipt(self.project)
        self.assertFalse(valid)
        self.assertIn('implementation', reason)

    def test_modified_dataset_fails_gate(self):
        data_dir = self.project / '_inputs' / 'data'
        data_dir.mkdir(parents=True)
        (data_dir / 'a.csv').write_text('1,2,3')
        import_docker_run(self.project)
        (data_dir / 'a.csv').write_text('1,2,4')
        valid, reason = verify_run_receipt(self.project)
        self.assertFalse(valid)
        self.assertIn('dataset', reason)

    def test_modified_ledger_metrics_cannot_be_ignored(self):
        import_docker_run(self.project)
        ws = Workspace(self.project)
        run_dir = next(ws.runs_dir.iterdir())
        (run_dir / 'metrics.json').write_text('{"values":{"accuracy":0.01}}')
        self.assertFalse(verify_run_receipt(self.project)[0])

    def test_failed_sandbox_attempt_never_creates_evidence(self):
        self.good_results['attempts'][0]['run'] = 'FAIL'
        self.results_path.write_text(json.dumps(self.good_results))
        with self.assertRaisesRegex(ValueError, 'not successful'):
            import_docker_run(self.project)
        self.assertFalse((self.project / 'research').exists())

    def test_incomplete_results_never_imported(self):
        self.good_results['values'] = {}
        self.results_path.write_text(json.dumps(self.good_results))
        with self.assertRaisesRegex(ValueError, 'contract failed'):
            import_docker_run(self.project)

    def test_reproduce_refuses_replay_on_host(self):
        import_docker_run(self.project)
        receipt = json.loads((self.project / 'control' / 'ledger_s4_receipt.json').read_text())
        with self.assertRaisesRegex(ValueError, 'cannot be replayed as a host command'):
            reproduce(Workspace(self.project), receipt['run_id'])

    def test_methodology_skills_are_real_and_bounded(self):
        for stage in ('idea', 'experiment', 'review'):
            guide = brief(stage)
            self.assertTrue(len(guide) <= 6200)
            self.assertIn('not evidence', guide)
        self.assertIn('experiment-design', brief('experiment'))

    def test_idea_record_is_idempotent(self):
        first = record_idea(self.project)
        self.assertEqual(first, record_idea(self.project))
        (self.project / '1_idea' / 'idea.md').write_text('# Completely new hypothesis\n')
        other = record_idea(self.project)
        self.assertNotEqual(first['claim_id'], other['claim_id'])

    def test_integrity_engine_updates_invalidate_stage_signature(self):
        from factory.pipeline.provenance import input_signature
        off = input_signature(self.project, 'S4', {})
        on = input_signature(self.project, 'S4', {'ledger_enabled': True})
        self.assertNotEqual(off, on)

    def test_context_rejects_non_boolean_ledger_flag(self):
        with self.assertRaisesRegex(ValueError, 'ledger_enabled'):
            validate_context({'ledger_enabled': 'yes'})

    def test_runner_never_invokes_host_experiment(self):
        with patch('researchledger.runner._execute_once', side_effect=AssertionError('host experiment execution forbidden')):
            import_docker_run(self.project)
        self.assertTrue(verify_run_receipt(self.project)[0])


if __name__ == '__main__':
    unittest.main()
