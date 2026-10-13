"""Bundled PaperOrchestra skill integration and no-API-key writer transports."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factory.integrations import paper_orchestra
from factory.steps import write
from factory.agents.session import run_session
from factory.config import validate_context


class PaperOrchestraSkillTests(unittest.TestCase):
    def test_bundled_skills_and_vendor_prompts_resolve_without_user_install(self):
        self.assertTrue(paper_orchestra.bundled_vendor_present())
        with mock.patch.object(paper_orchestra, 'EXTERNAL_SKILLS', Path('/__missing_skill__')):
            self.assertEqual(paper_orchestra.resolve_skills_dir(), ROOT / 'skills')
        self.assertIn(paper_orchestra.VENDOR_DIR,
                      paper_orchestra.writing_access_dirs(ROOT / 'skills'))
        for stage in ['paper-orchestra', 'paper-orchestra-outline',
                      'paper-orchestra-literature', 'paper-orchestra-sections',
                      'paper-orchestra-figures', 'paper-orchestra-refine']:
            path = ROOT / 'skills' / stage / 'SKILL.md'
            self.assertTrue(path.is_file(), f'missing bundled skill {stage}')
            self.assertIn('ResearchLedger', path.read_text(encoding='utf-8'))

    def test_explicit_missing_skill_fails_not_silent_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'skills not found'):
                paper_orchestra.resolve_skills_dir(d)

    def test_missing_vendor_prompt_fails_closed_for_bundled_skills(self):
        with mock.patch.object(paper_orchestra, 'VENDOR_DIR', Path('/__not_present__')):
            with self.assertRaisesRegex(ValueError, 'original prompts are missing'):
                paper_orchestra.writing_access_dirs(ROOT / 'skills')

    def test_skill_links_resolve_to_real_source_files(self):
        import re
        for p in (ROOT / 'skills').glob('paper-orchestra*/SKILL.md'):
            text = p.read_text(encoding='utf-8')
            for relative in re.findall(r'\]\((\.\./[^)#]+)\)', text):
                self.assertTrue((p.parent / relative).resolve().is_file(),
                                f'{p}: invalid link {relative}')

    def test_writing_prompt_explicitly_uses_bundled_source_and_no_fake_results(self):
        prompt = write.draft_prompt(ROOT / 'skills')
        self.assertIn('paper-orchestra/SKILL.md', prompt)
        self.assertIn('vendor/paperorchestra/methods/prompts', prompt)
        self.assertIn('\\PFVAL', prompt)
        self.assertIn('\\PFFIG', prompt)
        self.assertIn('no experiment', prompt.lower())

    def test_provider_selection_validation(self):
        validate_context({'writer_provider': 'codex'})
        validate_context({'writer_provider': 'claude'})
        with self.assertRaisesRegex(ValueError, 'writer_provider'):
            validate_context({'writer_provider': 'unknown'})

    def test_doctor_reports_bundled_skills_even_if_clis_missing(self):
        from factory.cli.main import doctor
        with mock.patch('factory.cli.main.AgentLoop') as loop:
            loop.return_value.healthcheck.return_value = {'status': 'BLOCK', 'reason': 'CLI_NOT_INSTALLED'}
            report = doctor()
        self.assertEqual(report['checks']['paperorchestra_skills']['status'], 'PASS')
        self.assertIn('skills', report['checks']['paperorchestra_skills']['detail'])


class CodexWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        stub_dir = self.base / 'bin'
        stub_dir.mkdir()
        self.work = self.base / 'work'
        self.work.mkdir()
        exe = stub_dir / 'codex'
        exe.write_text('#!/usr/bin/env python3\n'
                       'import json, os, pathlib, sys\n'
                       'argv=sys.argv[1:]\n'
                       'request=sys.stdin.read()\n'
                       'path=pathlib.Path(os.environ["CODEX_CAPTURE"])\n'
                       'path.write_text(json.dumps({"argv":argv, "stdin_len":len(request), "cwd":os.getcwd()}))\n'
                       'pathlib.Path(argv[argv.index("--output-last-message")+1]).write_text("written")\n'
                       'pathlib.Path("output.tex").write_text("ok")\n', encoding='utf-8')
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
        self.environment={'PATH':str(stub_dir)+os.pathsep+os.environ.get('PATH',''),
                          'CODEX_CAPTURE':str(self.base/'capture.json')}

    def test_codex_workspace_writer_reads_prompt_from_stdin(self):
        with mock.patch.dict(os.environ, self.environment):
            response=run_session('a'*120_000,self.work, ['Read','Write'],
                                 add_dirs=[ROOT/'skills', paper_orchestra.VENDOR_DIR],
                                 model='local-default', provider='codex')
        details=json.loads((self.base/'capture.json').read_text(encoding='utf-8'))
        self.assertEqual(details['stdin_len'],120_000)
        self.assertEqual(Path(details['cwd']),self.work)
        self.assertIn('workspace-write',details['argv'])
        self.assertNotIn('--add-dir',details['argv'])
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',details['argv'])
        self.assertTrue((self.work/'output.tex').is_file())
        self.assertEqual(response['stdout'],'written')

    def test_unsupported_provider_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'provider must'):
            run_session('prompt',self.work, [],provider='api')


if __name__ == '__main__':
    unittest.main()
