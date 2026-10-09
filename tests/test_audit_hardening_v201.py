"""Regressions found by the post-v2 source and release audit."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from factory import sandbox
from factory.science import literature, reproduction


class ReproductionSafetyTests(unittest.TestCase):
    def test_rejects_infinite_negative_and_overpermissive_tolerances(self):
        for a, r in [(float('inf'), 0), (float('nan'), 0), (-1, 0),
                     (1e8, 0), (0, .5), (True, 0)]:
            with self.subTest(a=a, r=r), self.assertRaisesRegex(ValueError, 'tolerances'):
                reproduction.repeat(Path('.'), abs_tol=a, rel_tol=r)
        self.assertTrue(reproduction._valid_tolerances(1e-7, 1e-5))
        self.assertFalse(reproduction._valid_tolerances(.011, 0))

    def test_reproduction_receipt_rejects_unsafe_tolerances_before_evidence_lookup(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            out = project / reproduction.OUT
            out.parent.mkdir(parents=True)
            out.write_text('{}')
            receipt = project / reproduction.RECEIPT
            receipt.write_text(json.dumps({'status': 'MATCHED_WITHIN_TOLERANCE',
                                           'comparison': {'abs_tol': 1e9, 'rel_tol': 0,
                                                          'problems': []}}))
            ok, problems = reproduction.check(project)
            self.assertFalse(ok)
            self.assertIn('tolerances', ' '.join(problems))

    def test_reproduction_rejects_symlinked_parent_directory(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            project = Path(d)
            (project / 'control').mkdir()
            (Path(outside) / 'run').mkdir()
            (Path(outside) / 'run' / 'results.json').write_text('{}')
            (project / 'control/independent_repeat_output').symlink_to(outside, target_is_directory=True)
            (project / reproduction.RECEIPT).write_text('{}')
            ok, errors = reproduction.check(project)
            self.assertFalse(ok)
            self.assertIn('unsafe', ' '.join(errors))


class DockerSafetyTests(unittest.TestCase):
    def test_rejects_symlink_mount_root_and_nested_dataset_links(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            real = root / 'real'; real.mkdir()
            linked = root / 'linked'; linked.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                sandbox._safe_mount(linked)
            child = real / 'child'; child.mkdir()
            with self.assertRaisesRegex(ValueError, 'symlink'):
                sandbox._safe_mount(linked / 'child')  # symlinked ancestor, not leaf
            (real / 'outside').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                sandbox._safe_mount(real, inspect_contents=True)

    def test_no_docker_process_started_when_dataset_is_symlink(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repo = root / 'repo'; repo.mkdir()
            data = root / 'data'; data.symlink_to(repo, target_is_directory=True)
            with patch('factory.sandbox.shutil.which', return_value='/usr/bin/docker'), \
                    patch('factory.sandbox.subprocess.run') as run:
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    sandbox.Sandbox().run(repo, ['python', 'pf_run.py'], root / 'out', data=data)
                run.assert_not_called()


class LiteratureSafetyTests(unittest.TestCase):
    def test_corrupt_literature_entries_are_rejected_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            reg = root / literature.REGISTRY
            reg.parent.mkdir()
            reg.write_text(json.dumps({'schema_version': 1, 'works': [None]}))
            def fetch(_):
                return {'message': {'DOI': '10.1234/valid', 'title': ['Valid title']}}
            with self.assertRaisesRegex(ValueError, 'non-object'):
                literature.verify_doi(root, '10.1234/valid', fetch=fetch)


class PackagingTests(unittest.TestCase):
    def test_custom_workspace_directory_is_used_in_new_process(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, PAPERFACTORY_WORKSPACES=d)
            value = subprocess.check_output([sys.executable, '-c',
                'from factory.cli.main import WORKSPACES; print(WORKSPACES)'],
                env=env, text=True).strip()
            self.assertEqual(Path(value), Path(d))


class StreamingHashTests(unittest.TestCase):
    def test_tree_hash_is_backward_compatible_and_refuses_symlinks(self):
        import hashlib
        from factory.steps.code import tree_hash
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'one.py').write_text('print(1)')
            (root / 'two.txt').write_text('hello')
            old = hashlib.sha256()
            for file in sorted(root.rglob('*')):
                old.update(file.relative_to(root).as_posix().encode())
                old.update(file.read_bytes())
            self.assertEqual(tree_hash(root), old.hexdigest())
            (root / 'link').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                tree_hash(root)


if __name__ == '__main__':
    unittest.main()
