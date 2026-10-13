"""Regressions for inputs, paper builds, and process management.

All tests are local: no LLM, Docker, network, or LaTeX installation required.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from factory.steps import idea, review
from researchledger.runner import _execute_once


class IdeaIntegrityTests(unittest.TestCase):
    def idea_row(self, name='a'):
        return {
            'id': name, 'title': 'Robust baseline', 'hypothesis': 'A measurable benefit exists',
            'falsifier': {'statement': 'The measured gain falls below one point',
                          'metric': 'gain', 'threshold': 1},
            'reviews': [{**{'reviewer_id': rid}, **dict.fromkeys(idea.SCORE_FIELDS, 6)}
                        for rid in ('r1', 'r2')],
        }

    def test_nonfinite_review_scores_never_rank(self):
        for invalid in (float('nan'), float('inf'), float('-inf'), True):
            row = self.idea_row()
            row['reviews'][0]['novelty'] = invalid
            with self.subTest(score=invalid), self.assertRaisesRegex(ValueError, 'invalid novelty'):
                idea.score(row)

    def test_invalid_review_structures_fail_cleanly(self):
        for invalid in (None, {}, 'bad', [None, None], [{'reviewer_id': 'r1'}]):
            row = self.idea_row()
            row['reviews'] = invalid
            with self.subTest(reviews=invalid), self.assertRaises(ValueError):
                idea.score(row)

    def test_malformed_candidate_is_a_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for corrupt in (None, {'id': ['not-a-string'], 'title': 'T', 'hypothesis': 'H'},
                            {'id': ' ', 'title': 'T', 'hypothesis': 'H'}):
                source = root / 'input.json'
                source.write_text(json.dumps([corrupt, self.idea_row('b')]))
                with self.subTest(candidate=corrupt), self.assertRaises(ValueError):
                    idea.select(root, source)

    def test_generated_idea_identifiers_must_be_unique(self):
        candidate = self.idea_row('same')
        candidate.pop('reviews')
        class FakeAgent:
            def run(self, prompt, validator, schema_path=None):
                payload = {'ideas': [candidate, candidate.copy()]}
                issues = validator(payload)
                if issues:
                    raise ValueError('; '.join(issues))
                return {'payload': payload}
        with self.assertRaisesRegex(ValueError, 'unique'):
            idea.generate('testing', lambda: FakeAgent())


class LatexIntegrityTests(unittest.TestCase):
    def test_bibtex_failures_are_not_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'paper.aux').write_text(r'\bibdata{refs}')
            def fake_run(command, **kwargs):
                if command[0] == 'bibtex':
                    return subprocess.CompletedProcess(command, 1, stdout='Bad bibliography', stderr='')
                (root / 'paper.pdf').write_bytes(b'%PDF')
                return subprocess.CompletedProcess(command, 0, stdout='ok', stderr='')
            with mock.patch('factory.steps.review.shutil.which', side_effect=lambda x: x), \
                 mock.patch('factory.steps.review.subprocess.run', side_effect=fake_run):
                with self.assertRaisesRegex(ValueError, 'BibTeX failed'):
                    review.compile_pdf(root)

    def test_latex_failure_after_bibtex_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'paper.aux').write_text(r'\bibdata{refs}')
            calls = {'tex': 0}
            def fake_run(command, **kwargs):
                if command[0] == 'bibtex':
                    return subprocess.CompletedProcess(command, 0, stdout='', stderr='')
                calls['tex'] += 1
                return subprocess.CompletedProcess(command, 2 if calls['tex'] == 2 else 0,
                                                   stdout='bad cross refs', stderr='')
            with mock.patch('factory.steps.review.shutil.which', side_effect=lambda x: x), \
                 mock.patch('factory.steps.review.subprocess.run', side_effect=fake_run):
                with self.assertRaisesRegex(ValueError, 'rebuild after BibTeX failed'):
                    review.compile_pdf(root)

    def test_bibliography_requires_bibtex(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'paper.aux').write_text(r'\bibdata{refs}')
            with mock.patch('factory.steps.review.shutil.which',
                            side_effect=lambda x: None if x == 'bibtex' else x), \
                 mock.patch('factory.steps.review.subprocess.run',
                            return_value=subprocess.CompletedProcess([], 0, stdout='', stderr='')):
                with self.assertRaisesRegex(ValueError, 'bibtex.*not installed'):
                    review.compile_pdf(root)


@unittest.skipUnless(os.name == 'posix', 'POSIX subprocess groups only')
class RunProcessTests(unittest.TestCase):
    def test_timeout_kills_descendants_holding_stdout_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent_program = (
                "import subprocess, sys, time\n"
                "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
                "time.sleep(20)\n"
            )
            started = time.monotonic()
            code, timed_out = _execute_once(
                [sys.executable, '-c', parent_program], cwd=root, env=dict(os.environ),
                stdout_path=root / 'stdout.log', stderr_path=root / 'stderr.log', timeout=0.3,
            )
            self.assertTrue(timed_out)
            self.assertNotEqual(code, 0)
            self.assertLess(time.monotonic() - started, 5.0)


if __name__ == '__main__':
    unittest.main()

class StreamSafetyTests(unittest.TestCase):
    def test_stream_logs_are_bounded_without_stopping_drain(self):
        from io import StringIO
        from researchledger.runner import _pump
        source = StringIO('a' * 100_000)  # deliberately no newline
        logfile, echo = StringIO(), StringIO()
        _pump(source, logfile, echo, max_chars=100)
        self.assertIn('output truncated', logfile.getvalue())
        self.assertEqual(logfile.getvalue()[:100], 'a' * 100)
        self.assertLess(len(logfile.getvalue()), 300)
        self.assertEqual(echo.getvalue(), logfile.getvalue())

class IdeaVendorTests(unittest.TestCase):
    def test_bundled_agent_is_inspectable_and_preparable_without_execution(self):
        from factory.integrations.idea_discovery import inspect, prepare
        self.assertEqual(inspect()['status'], 'AVAILABLE')
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            report = prepare(project)
            self.assertEqual(report['status'], 'PREPARED_NOT_EXECUTED')
            target = Path(report['path'])
            self.assertTrue((target / 'scripts' / 'run_pipeline.py').is_file())
            self.assertFalse((target / '.env').exists())
            with self.assertRaisesRegex(ValueError, 'already prepared'):
                prepare(project)

    def test_vendor_rejects_archive_traversal_and_symlink_in_parent(self):
        from factory.integrations import idea_discovery
        from zipfile import ZipFile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'malicious.zip'
            with ZipFile(archive, 'w') as handle:
                handle.writestr('idea-discovery-v5/README.md', 'fake')
                handle.writestr('idea-discovery-v5/scripts/run_pipeline.py', 'code')
                handle.writestr('idea-discovery-v5/ARCHITECTURE.md', 'arch')
                handle.writestr('idea-discovery-v5/requirements.txt', '')
                handle.writestr('idea-discovery-v5/../../escape.txt', 'bad')
            with mock.patch.object(idea_discovery, 'ARCHIVE', archive):
                with self.assertRaisesRegex(ValueError, 'unsafe'):
                    idea_discovery.prepare(root)
            self.assertFalse((root / 'escape.txt').exists())
            (root / '_vendor').symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'unsafe symlink'):
                idea_discovery.prepare(root)
