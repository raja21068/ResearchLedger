"""Offline fake-CLI transport tests: NOT real language model reviews."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from factory.integrations.subscription_bridge import call_subscription_cli, cli_status
from factory.integrations.idea_discovery import prepare, _install_subscription_shim, run
from factory.steps.review import _settings
from factory.config import validate_context
from factory.agents.loop import AgentLoop


@pytest.fixture()
def fake_bin(tmp_path, monkeypatch):
    bin_dir=tmp_path/'bin'
    bin_dir.mkdir()
    script='''#!/usr/bin/env python3
import json, pathlib, sys
args=sys.argv[1:]
if args[:2] in (['auth','status'],['login','status']):
    print('{"loggedIn": true}')
    sys.exit(0)
_ = sys.stdin.read()
if '--output-last-message' in args:
    pathlib.Path(args[args.index('--output-last-message')+1]).write_text('{"valid": true}',encoding='utf-8')
else:
    print(json.dumps({"structured_output": {"valid": True}}))
'''
    for name in ('claude','codex'):
        exe=bin_dir/name
        exe.write_text(script,encoding='utf-8')
        exe.chmod(0o755)
    monkeypatch.setenv('PATH',str(bin_dir)+os.pathsep+os.environ.get('PATH',''))
    return bin_dir


@pytest.mark.parametrize('provider',['claude','codex'])
def test_no_key_subscription_cli_transport(fake_bin,monkeypatch,provider):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    assert cli_status(provider)['status']=='AVAILABLE'
    actual=call_subscription_cli(provider,system='Check',user='Test',schema={'type':'object','properties':{'valid':{'type':'boolean'}},'required':['valid']})
    assert json.loads(actual)=={'valid':True}


@pytest.mark.parametrize('provider',['claude','codex'])
def test_existing_factory_loop_with_cli(fake_bin,provider,tmp_path):
    agent=AgentLoop(provider=provider,workdir=tmp_path,max_turns=1,budget_seconds=10)
    result=agent.run('Return {"valid": true}',lambda x: [] if x.get('valid') else ['missing valid'])
    assert result['status']=='PASS'
    assert not result['replayed']


def test_v5_shim_works_in_prepared_copy_only(fake_bin,tmp_path,monkeypatch):
    project=tmp_path/'project'
    project.mkdir()
    before=prepare(project)
    original=Path(before['path'])/'scripts'/'utils.py'
    original_source=original.read_text(encoding='utf-8')
    _install_subscription_shim(Path(before['path']))
    _install_subscription_shim(Path(before['path']))
    assert original.read_text(encoding='utf-8').count('# BEGIN RESEARCHLEDGER_SUBSCRIPTION_CLI_SHIM_v1')==1
    assert original_source != original.read_text(encoding='utf-8')
    env=dict(os.environ)
    env['RESEARCHLEDGER_V5_PROVIDER']='codex'
    root=Path(__file__).resolve().parents[1]
    env['PYTHONPATH']=str(root)
    code="import sys;sys.path.insert(0,sys.argv[1]);from utils import ClaudeClient;assert ClaudeClient().ask_json('Review','Return JSON')['valid'] is True"
    proc=subprocess.run([sys.executable,'-c',code,str(Path(before['path'])/'scripts')],env=env,capture_output=True,text=True,timeout=30)
    assert proc.returncode==0,proc.stderr


def test_v5_can_dry_run_without_key_or_cli(tmp_path):
    project=tmp_path/'project';project.mkdir()
    paper=tmp_path/'paper.md';paper.write_text('# Example scientific paper')
    info=run(project,topic='Investigate testability',papers=[paper],provider='codex',dry_run=True)
    assert info['status']=='DRY_RUN' and info['model_provider']=='codex'


def test_factory_settings_select_one_subscription_provider():
    context={'review_agent':'beihang-native','referee_provider':'codex'}
    validate_context(context)
    assert _settings(context)['provider']=='codex'
    assert _settings({**context,'review_provider':'claude'})['provider']=='claude'
