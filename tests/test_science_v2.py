"""Offline evidence-first regression tests; no host execution or external network."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from factory.config import validate_context
from factory.pipeline.provenance import hash_file
from factory.science import protocol, claims, literature, reproduction


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='pf-v2-protocol-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / '1_idea').mkdir()
        (self.root / '1_idea/idea.md').write_text('A prospective falsifiable hypothesis')
        (self.root / '_inputs/data').mkdir(parents=True)
        (self.root / '_inputs/data/data.csv').write_text('x,y\n1,2\n')
        protocol.scaffold(self.root)
        self.file = self.root / protocol.PROTOCOL
        self.spec = json.loads(self.file.read_text())
        self.spec.update(question='Does our treatment measurably change response?',
                         hypothesis='Our predefined metric differs from the baseline.',
                         falsifier='The measured effect falls below a preregistered threshold.',
                         analysis_type='confirmatory', operator_acknowledgement=True)
        self.spec['dataset'].update(name='sample', version='v1', source='curated public dataset',
                                    split_strategy='patient-independent fold split',
                                    license_reviewed=True, unit_of_independence='subject')
        self.spec['design'].update(primary_metric='accuracy', primary_baseline='control',
                                   analysis_plan='compare prespecified paired subjects',
                                   ablation_plan='exclude feature X', random_seeds=[7, 13],
                                   limitations='small pilot dataset limits generalization')
        self.file.write_text(json.dumps(self.spec))

    def test_protocol_is_locked_before_confirmatory_run(self):
        receipt = protocol.lock(self.root)
        self.assertEqual(receipt['protocol_sha256'], hash_file(self.file))
        self.assertTrue(protocol.check(self.root, {'science_mode':'validation'})[0])
        (self.root / '_inputs/data/data.csv').write_text('x,y\n1,3\n')
        ok, messages = protocol.check(self.root, {'science_mode':'validation'})
        self.assertFalse(ok)
        self.assertIn('dataset changed', ';'.join(messages))

    def test_locked_protocol_rejects_hidden_edits_and_relocking(self):
        protocol.lock(self.root)
        self.spec['hypothesis'] += ' appended post hoc'
        self.file.write_text(json.dumps(self.spec))
        self.assertFalse(protocol.check(self.root, {'science_mode':'validation'})[0])
        with self.assertRaisesRegex(ValueError, 'already locked'):
            protocol.lock(self.root)

    def test_unconfirmed_protocol_is_not_lockable(self):
        self.spec['operator_acknowledgement'] = False
        self.file.write_text(json.dumps(self.spec))
        with self.assertRaisesRegex(ValueError, 'operator_acknowledgement'):
            protocol.lock(self.root)

    def test_validation_requires_dataset_and_ledger(self):
        self.assertRaises(ValueError, validate_context, {'science_mode':'validation', 'ledger_enabled':False})
        shutil.rmtree(self.root / '_inputs/data')
        with self.assertRaisesRegex(ValueError, 'real dataset'):
            protocol.lock(self.root)

    def test_dataset_symlink_is_not_permitted(self):
        outside = self.root / 'outside.csv'
        outside.write_text('secret')
        (self.root / '_inputs/data/link.csv').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            protocol.lock(self.root)

    def test_post_idea_protocol_does_not_make_idea_checkpoint_stale(self):
        from factory.pipeline.provenance import input_signature
        context = {'science_mode':'validation','ledger_enabled':True}
        before_s1 = input_signature(self.root, 'S1', context)
        before_s4 = input_signature(self.root, 'S4', context)
        protocol.lock(self.root)
        self.assertEqual(before_s1, input_signature(self.root, 'S1', context))
        self.assertNotEqual(before_s4, input_signature(self.root, 'S4', context))
        (self.root / '_inputs/metric_claims.json').write_text('{"schema_version":1,"claims":[]}')
        self.assertEqual(before_s1, input_signature(self.root, 'S1', context))

    def test_registered_seed_statistics_reject_cherry_picked_aggregate(self):
        from factory.science.statistics import summarize
        good = {'values':{'accuracy':0.85}, 'seed_metrics':{'accuracy':[0.8,0.9]}}
        self.assertEqual(summarize(good, primary_metric='accuracy', seeds=[1,2])['status'],'PASS')
        good['values']['accuracy'] = 0.9
        self.assertEqual(summarize(good, primary_metric='accuracy', seeds=[1,2])['status'],'BLOCKED')

    def test_validation_mode_rejects_missing_real_data_seed_attestation(self):
        from factory.steps.code import _validate_data_attestation
        protocol.lock(self.root)
        payload={'values':{'accuracy':0.85}, 'data_source':'provided', 'n_samples':10,
                 'seeds':[7,13], 'seed_metrics':{'accuracy':[0.8,0.9]}}
        _validate_data_attestation(self.root, payload)
        payload['seeds']=[7]
        with self.assertRaisesRegex(ValueError, 'all locked random seeds'):
            _validate_data_attestation(self.root, payload)


class LiteratureTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='pf-v2-lit-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / '_inputs').mkdir()

    def test_doi_resolution_checks_identity_and_metadata_only(self):
        def fake_fetch(url):
            self.assertIn('api.crossref.org/works/10.', url)
            return {'message': {'DOI': '10.1234/test-paper', 'title': ['Evidence Paper'],
                                'published': {'date-parts': [[2024, 1]]}}}
        result = literature.verify_doi(self.root, 'https://doi.org/10.1234/test-paper', fetch=fake_fetch)
        self.assertEqual(result['metadata_status'], 'CROSSREF_RESOLVED')
        self.assertIn('NOT_FINDING_VALIDATION', result['scope'])
        self.assertEqual(literature.audit(self.root)['status'], 'BLOCKED')
        literature.scaffold_prior_art(self.root)
        path = self.root / literature.PRIOR_ART
        info = json.loads(path.read_text())
        info.update(novelty_claim='We address a different outcome on a prespecified split.',
                    researcher_acknowledgement=True,
                    nearest_prior_art=[{'doi':'10.1234/test-paper',
                                        'overlap':'Both methods measure the same outcome.',
                                        'difference':'Our experiment uses a different evaluation.',
                                        'limitation':'The existing method cannot study sparse data.'}])
        path.write_text(json.dumps(info))
        self.assertEqual(literature.audit(self.root)['status'], 'PASS')

    def test_editing_registry_only_cannot_preserve_verified_status(self):
        literature.verify_doi(self.root, '10.1234/checked', fetch=lambda url:{'message':{
            'DOI':'10.1234/checked','title':['Original title'], 'issued':{'date-parts':[[2020]]}}})
        registry_path=self.root/literature.REGISTRY
        body=json.loads(registry_path.read_text())
        body['works'][0]['title']='Forged replacement title'
        registry_path.write_text(json.dumps(body))
        report=literature.audit(self.root)
        self.assertEqual(report['verified_dois'],0)
        self.assertIn('receipt', ';'.join(report['issues']))

    def test_crossref_mismatched_response_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'does not match'):
            literature.verify_doi(self.root, '10.1234/real',
                                  fetch=lambda _: {'message': {'DOI':'10.1234/evil','title':['A']}})
        self.assertFalse((self.root / literature.REGISTRY).exists())

    def test_doi_rejects_non_doi_urls(self):
        with self.assertRaises(ValueError):
            literature.normalize_doi('https://evil.example/redirect')


class ClaimAndRepeatTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='pf-v2-results-'))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        for path in ('1_idea', '2_paper', '4_code/repo'):
            (self.root / path).mkdir(parents=True)
        (self.root / '1_idea/idea.md').write_text('# Hypothesis\n\nA difference in response is falsifiable')
        (self.root / '2_paper/results_spec.json').write_text(json.dumps({
            'slots':[{'id':'dice','kind':'value','describe':'real metric'},
                     {'id':'auc','kind':'value','describe':'real AUC'}]}))
        (self.root / '4_code/repo/pf_run.py').write_text('# stub; never executed')
        from factory.steps.code import tree_hash
        (self.root / '4_code/results.json').write_text(json.dumps({
            'values': {'dice': 0.8, 'auc': 0.9}, 'series':{}, 'scale':'pilot',
            'image':'python@sha256:'+'a'*64, 'repo_sha256':tree_hash(self.root/'4_code/repo'),
            'command':['python','pf_run.py'],
            'attempts':[{'install':'PASS','run':'PASS','returncode':0,'problems':[]}]}))
        (self.root / '4_code/experimental_log.generated.md').write_text('Measured pilot')
        (self.root / '4_code/unresolved.json').write_text('[]')
        from factory.integrations.ledger import record_idea, import_docker_run
        record_idea(self.root)
        import_docker_run(self.root)
        claims.scaffold(self.root)
        path = self.root / claims.CLAIMS
        self.body = json.loads(path.read_text())
        for row in self.body['claims']:
            row.update(statement=f"Measured {row['metric_id']} on the frozen pilot data.",
                       population='synthetic pilot cohort', analysis='exploratory')
        path.write_text(json.dumps(self.body))

    def test_numeric_claim_bindings_are_measured_not_verified(self):
        report = claims.evaluate(self.root, write=True)
        self.assertEqual(report['status'], 'PASS')
        self.assertTrue(claims.check(self.root)[0])
        self.assertEqual(report['claims'][0]['status'], 'MEASURED_NOT_SCIENTIFICALLY_VERIFIED')
        self.assertEqual(report['coverage'], 'DECLARED_RESULT_SLOTS_ONLY')
        self.assertEqual(reproduction.check(self.root)[0], False)

    def test_undeclared_metric_blocks_binding(self):
        self.body['claims'].pop()
        (self.root / claims.CLAIMS).write_text(json.dumps(self.body))
        result = claims.evaluate(self.root, write=True)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertIn('auc', ';'.join(result['problems']))
        self.assertFalse((self.root / claims.BINDINGS).exists())

    def test_tampering_invalidates_bound_results(self):
        claims.evaluate(self.root, write=True)
        payload = json.loads((self.root / '4_code/results.json').read_text())
        payload['values']['dice'] = 0.99
        (self.root / '4_code/results.json').write_text(json.dumps(payload))
        self.assertFalse(claims.check(self.root)[0])

    def test_isolated_repeat_compares_series_as_well_as_values(self):
        a = {'values':{'dice':0.8},'series':{'curve':{'x':[0,1], 'series':{'model':[0.4,0.8]}}}}
        b = {'values':{'dice':0.8+1e-6},'series':{'curve':{'x':[0,1], 'series':{'model':[0.4,0.81]}}}}
        self.assertTrue(reproduction._compare(a, b, abs_tol=1e-5, rel_tol=1e-5))
        b['series']['curve']['series']['model'][1] = .8
        self.assertFalse(reproduction._compare(a, b, abs_tol=1e-5, rel_tol=1e-5))

    def test_independent_repeat_never_executes_code_on_host(self):
        class FakeSandbox:
            image = 'python@sha256:'+'a'*64
            def install(self, repo, deps):
                deps.mkdir(parents=True)
                return {'status':'PASS'}
            def run(self, repo, command, out_dir, **kwargs):
                out_dir.mkdir(parents=True)
                (out_dir / 'results.json').write_text(json.dumps({'values':{'dice':0.8,'auc':0.9}}))
                return {'status':'PASS', 'returncode':0}
        record = reproduction.repeat(self.root, sandbox=FakeSandbox())
        self.assertEqual(record['status'], 'MATCHED_WITHIN_TOLERANCE')
        self.assertTrue(reproduction.check(self.root)[0])
        (self.root / 'control/independent_repeat_output/run/results.json').write_text('tampered')
        self.assertFalse(reproduction.check(self.root)[0])

if __name__ == '__main__':
    unittest.main()
