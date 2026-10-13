"""Opt-in, non-executing preparation of the bundled Idea Discovery v5 tool.

This module deliberately does not silently run another research agent or
interpret its report as a verified hypothesis. It only makes the vendored
source available in a dedicated workspace after safe archive validation.
"""
from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

from factory.pipeline.provenance import hash_file

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / 'vendor' / 'idea-generation' / 'idea-discovery-v5.zip'
DISTRIBUTION = 'idea-discovery-v5'
MAX_FILES = 500
MAX_EXTRACTED_BYTES = 25_000_000


def _entries(archive):
    if not archive.is_file() or archive.is_symlink():
        raise ValueError('bundled Idea Discovery v5 archive unavailable or unsafe')
    try:
        with ZipFile(archive) as handle:
            entries = handle.infolist()
            if not entries or len(entries) > MAX_FILES:
                raise ValueError('unexpected Idea Discovery archive size')
            total = 0
            for entry in entries:
                name = entry.filename
                segments = PurePosixPath(name).parts
                if ('\\' in name or ':' in name or not segments or
                        segments[0] != DISTRIBUTION or
                        any(segment in ('', '.', '..') for segment in segments) or
                        name.startswith('/') or entry.file_size > MAX_EXTRACTED_BYTES):
                    raise ValueError('unsafe Idea Discovery archive entry')
                type_bits = stat.S_IFMT(entry.external_attr >> 16)
                if type_bits not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError('Idea Discovery archive contains symlink or special file')
                total += entry.file_size
                if total > MAX_EXTRACTED_BYTES:
                    raise ValueError('Idea Discovery archive expands beyond safety limit')
            required = {
                'idea-discovery-v5/README.md',
                'idea-discovery-v5/scripts/run_pipeline.py',
                'idea-discovery-v5/requirements.txt',
                'idea-discovery-v5/ARCHITECTURE.md',
            }
            if not required.issubset({item.filename for item in entries}):
                raise ValueError('Idea Discovery archive is missing essential components')
            return entries, total
    except BadZipFile as exc:
        raise ValueError('Idea Discovery archive is corrupt') from exc


def inspect():
    entries, total = _entries(ARCHIVE)
    return {'status': 'AVAILABLE', 'bundle': DISTRIBUTION,
            'archive_sha256': hash_file(ARCHIVE), 'files': len(entries),
            'uncompressed_bytes': total, 'execution': 'NOT_EXECUTED',
            'note': 'V5 runs separately and requires its own dependencies and API configuration; '
                    'its scores are not evidence of measured scientific novelty.'}


def prepare(project):
    """Extract the verified archive to PROJECT/_vendor/idea-discovery-v5.

    Existing copies are never overwritten. No bundled scripts are executed.
    """
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError('project workspace is missing')
    entries, _ = _entries(ARCHIVE)
    destination_parent = project / '_vendor'
    if destination_parent.is_symlink():
        raise ValueError('unsafe symlink for vendor target')
    destination_parent.mkdir(exist_ok=True)
    destination = destination_parent / DISTRIBUTION
    if destination.exists() or destination.is_symlink():
        raise ValueError('Idea Discovery v5 is already prepared; refusing overwrite')
    # A staging directory avoids exposing partial vendor trees on extraction failure.
    with tempfile.TemporaryDirectory(prefix='.idea-discovery-', dir=destination_parent) as temporary:
        stage = Path(temporary)
        with ZipFile(ARCHIVE) as handle:
            for entry in entries:
                segments = PurePosixPath(entry.filename).parts
                relative = Path(*segments[1:])
                target = stage / relative
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with handle.open(entry) as source, target.open('xb') as output:
                        shutil.copyfileobj(source, output, length=64 * 1024)
        if not (stage / 'scripts' / 'run_pipeline.py').is_file():
            raise ValueError('incomplete Idea Discovery extraction')
        os.replace(stage, destination)
    return {'status': 'PREPARED_NOT_EXECUTED', 'path': str(destination),
            'archive_sha256': hash_file(ARCHIVE),
            'next': 'Read README.md, install its dependencies, supply verified papers, '
                    'configure an API key privately, then run its pipeline explicitly. '
                    'Generated MVE protocols must be executed and evaluated separately.'}


def run(project, *, topic=None, papers=(), skip_embeddings=True, no_quality=False,
        timeout=3600, dry_run=False, provider='api'):
    """Run actual V5 CLI in the project's prepared, separated tool workspace.

    V5 operates on local copies of user-supplied papers. This does not imply
    novelty verification or execution of its proposed experiments.
    """
    import importlib.util
    import json
    import subprocess
    import sys
    if provider not in {'api','claude','codex'}:
        raise ValueError('V5 provider must be api, claude or codex')
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError('project workspace not found')
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 14400:
        raise ValueError('timeout must be 1..14400 seconds')
    prepared = project / '_vendor' / DISTRIBUTION
    if not prepared.exists():
        prepare(project)
    if prepared.is_symlink() or (project / '_vendor').is_symlink() or not (prepared / 'scripts' / 'run_pipeline.py').is_file():
        raise ValueError('prepared Idea Discovery V5 installation is incomplete or unsafe')
    input_dir = prepared / 'input_papers'
    if input_dir.is_symlink():
        raise ValueError('unsafe input_papers symlink')
    input_dir.mkdir(exist_ok=True)
    provided = list(papers or ())
    for name in provided:
        raw_source = Path(name).expanduser()
        if raw_source.is_symlink():
            raise ValueError(f'unsafe source paper symlink: {name}')
        source = raw_source.resolve()
        if not source.is_file() or source.suffix.lower() not in {'.pdf', '.md', '.txt'}:
            raise ValueError(f'unsupported or missing source paper: {name}')
        if source.stat().st_size > 20_000_000:
            raise ValueError('input paper exceeds 20 MB safety limit')
        target = input_dir / source.name
        if target.is_symlink():
            raise ValueError(f'unsafe input paper symlink: {source.name}')
        if target.exists():
            if target.read_bytes() != source.read_bytes():
                raise ValueError(f'conflicting input paper filename: {source.name}')
        elif not dry_run:
            shutil.copyfile(source, target)
    corpus = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in {'.pdf', '.txt', '.md'} and p.name != 'README.md')
    if not corpus and not provided:
        raise ValueError('Idea Discovery V5 needs real source papers; use --paper PATH (one or more)')
    if not topic:
        topic_path = project / '_inputs' / 'topic.md'
        if topic_path.is_file():
            topic = topic_path.read_text(encoding='utf-8').strip()
    if not topic or not str(topic).strip():
        raise ValueError('provide --topic or _inputs/topic.md')
    args = [sys.executable, 'scripts/run_pipeline.py', '--topic', str(topic)]
    if skip_embeddings:
        args.append('--skip-embeddings')
    if no_quality:
        args.append('--no-quality')
    readiness = {'bundle': DISTRIBUTION, 'engine': 'NATIVE_V5', 'topic': str(topic),
                 'source_papers': [str(p) for p in corpus] + ([str(Path(p).resolve()) for p in provided] if dry_run else []),
                 'command': args, 'workspace': str(prepared),
                 'no_auto_execution_of_proposed_experiments': True,
                 'model_provider': provider, 'model_auth': 'existing CLI login' if provider != 'api' else 'API',
                 'not_a_verified_novelty_claim': True}
    if dry_run:
        return {'status': 'DRY_RUN', **readiness}
    if provider == 'api':
        if importlib.util.find_spec('anthropic') is None:
            raise ValueError('Idea Discovery V5 requires anthropic: install its dependencies in your own environment')
        if not os.environ.get('ANTHROPIC_API_KEY'):
            raise ValueError('ANTHROPIC_API_KEY is required in API mode; use --provider claude or codex for a subscription CLI')
    else:
        from factory.integrations.subscription_bridge import cli_status
        availability=cli_status(provider)
        if availability['status'] != 'AVAILABLE':
            raise ValueError(f"{provider} subscription CLI unavailable: {availability['reason']}")
        _install_subscription_shim(prepared)
    env=dict(os.environ)
    if provider != 'api':
        env['RESEARCHLEDGER_V5_PROVIDER']=provider
        env['PYTHONPATH']=str(ROOT)+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    try:
        cp = subprocess.run(args, cwd=prepared, env=env, capture_output=True, text=True,
                            errors='replace', shell=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f'Idea Discovery V5 timed out after {timeout} seconds') from exc
    logs = prepared / 'logs'
    logs.mkdir(exist_ok=True)
    # Do not serialize environment variables or potential credential strings.
    log = logs / 'researchctl_last_run.log'
    combined = cp.stdout[-100_000:] + '\n' + cp.stderr[-30_000:]
    key = os.environ.get('ANTHROPIC_API_KEY')
    if key:
        combined = combined.replace(key, '[REDACTED]')
    log.write_text(combined, encoding='utf-8')
    if cp.returncode:
        raise ValueError('Idea Discovery V5 failed; see ' + str(log) + ': ' + cp.stderr[-700:])
    summary = prepared / 'output' / 'falsification_summary.json'
    return {'status': 'EXECUTED_NOT_SCIENTIFICALLY_VERIFIED', **readiness,
            'log_path': str(log), 'report_path': str(prepared / 'output' / 'FINAL_REPORT.md'),
            'falsification_summary': str(summary) if summary.is_file() else None}


def adopt(project, *, idea_id, metric, threshold, falsifier_statement,
          operator_acknowledgement=False, strict_phases=False):
    """Explicitly bridge a V5 survivor into Factory S1 without invented scores.

    The operator provides the numeric rejection criterion: V5's multi-part
    hypothesis/MVE protocol cannot be losslessly mapped to a single number.
    No V5 result is promoted to verified science by importing it.
    """
    import json
    import math
    from factory.io import atomic_json
    project = Path(project).resolve()
    if not operator_acknowledgement:
        raise ValueError('operator must acknowledge the selected V5 idea and supplied falsifier')
    if not isinstance(idea_id, str) or not idea_id.strip():
        raise ValueError('non-empty --idea-id is required')
    if not isinstance(metric, str) or not metric.strip():
        raise ValueError('non-empty measurable --metric is required')
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
        raise ValueError('numeric finite --threshold is required')
    if not isinstance(falsifier_statement, str) or len(falsifier_statement.split()) < 5:
        raise ValueError('a concrete falsifier statement with at least five words is required')
    source = project / '_vendor' / DISTRIBUTION / 'output' / 'falsification_summary.json'
    if not source.is_file() or source.is_symlink():
        raise ValueError('native V5 falsification summary is missing; run V5 first')
    try:
        report = json.loads(source.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError('invalid V5 falsification summary') from exc
    entries = [x for x in report.get('ideas', []) if isinstance(x, dict) and x.get('idea_id') == idea_id]
    if len(entries) != 1:
        raise ValueError('requested V5 idea not uniquely present in falsification summary')
    record = entries[0]
    status = record.get('final_decision')
    if status not in {'READY_FOR_MVE', 'GREENLIGHT'}:
        raise ValueError('only READY_FOR_MVE or GREENLIGHT survivors may be adopted')
    if status == 'GREENLIGHT' and not record.get('mve_evidence_present'):
        raise ValueError('reported GREENLIGHT has no MVE evidence flag; refusing import')
    if strict_phases:
        phase_status = phase_audit(project, idea_id=idea_id)
        if phase_status['status'] != 'ARTIFACTS_RECORDED_NOT_SCIENTIFICALLY_VERIFIED':
            raise ValueError('strict V5 adoption requires Phase 10-16 recorded artifacts; run phase-audit')
        if any(x.get('validation_errors') for phase in phase_status['phases'] for x in phase['rounds']):
            raise ValueError('V5 Phase 10-16 contains validation errors; refusing strict adoption')
    data = record.get('final_idea')
    if not isinstance(data, dict):
        raise ValueError('surviving V5 idea object is missing')
    hypothesis = data.get('hypothesis')
    statement = hypothesis.get('statement') if isinstance(hypothesis, dict) else None
    if not isinstance(statement, str) or not statement.strip():
        raise ValueError('V5 idea has no hypothesis statement')
    title = data.get('title')
    if not isinstance(title, str) or not title.strip():
        raise ValueError('V5 idea has no title')
    method_sketch = data.get('method_sketch', {})
    if not isinstance(method_sketch, dict):
        raise ValueError('V5 method_sketch invalid')
    method = json.dumps(method_sketch, ensure_ascii=False)
    if not method_sketch:
        raise ValueError('V5 method_sketch is empty')
    adopted = {'schema_version': 1, 'source': 'IDEA_DISCOVERY_V5',
        'source_archive_sha256': hash_file(ARCHIVE),
        'source_report_sha256': hash_file(source), 'selected_id': idea_id,
        'v5_decision': status, 'mve_evidence_present': bool(record.get('mve_evidence_present')),
        'operator_acknowledged': True, 'phase_audit_required': bool(strict_phases),
        'idea': {'id': idea_id, 'title': title, 'hypothesis': statement, 'method': method,
                 'falsifier': {'metric': metric, 'threshold': threshold,
                               'statement': falsifier_statement}},
        'caveat': 'Imported research direction, not confirmed independent novelty or correctness. '
                  'READY_FOR_MVE has no executed MVE evidence. Numeric falsifier supplied by operator.'}
    target = project / '_inputs' / 'v5_adoption.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('V5 adoption already exists; refusing to silently overwrite selected idea')
    atomic_json(target, adopted)
    return {'status': 'ADOPTED_PENDING_FACTORY_S1', 'file': str(target),
            'v5_decision': status, 'verified_scientific_novelty': False}


def phase_audit(project, *, idea_id):
    """Verify V5 actually persisted Phase 10-16 evidence; fail closed on gaps.

    Artifact presence is NOT proof that LLM literature conclusions are correct.
    """
    import json
    project=Path(project).resolve()
    if not isinstance(idea_id,str) or not idea_id or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in idea_id):
        raise ValueError('invalid V5 idea ID')
    base=project/'_vendor'/DISTRIBUTION/'output'
    stages={
        10:('attack_loop','phase10_scorecard.json'),
        11:('attack_loop','phase11_novelty_attack.json'),
        12:('attack_loop','phase12_novelty_matrix.json'),
        13:('attack_loop','phase13_reviewer_attack.json'),
        14:('attack_loop','phase14_revision_or_kill.json'),
        15:('falsification','phase15_hypothesis_contract.json'),
        16:('falsification','phase16_occam_counterexample.json'),
    }
    entries=[]
    for number,(section,filename) in stages.items():
        root=base/section/idea_id
        round_paths=sorted(root.glob('round_*/'+filename)) if root.is_dir() and not root.is_symlink() else []
        valid=[]
        for path in round_paths:
            if path.is_symlink() or not path.is_file():continue
            try:
                artifact=json.loads(path.read_text(encoding='utf-8'))
                if isinstance(artifact,dict) and artifact:
                    valid.append({'path':str(path), 'sha256':hash_file(path),
                                  'validation_errors':artifact.get('_validation_errors',[])})
            except (ValueError,OSError): pass
        entries.append({'phase':number,'artifact':filename,'stage':section,
                        'status':'RECORDED' if valid else 'MISSING',
                        'rounds':valid})
    status='ARTIFACTS_RECORDED_NOT_SCIENTIFICALLY_VERIFIED' if all(x['status']=='RECORDED' for x in entries) else 'INCOMPLETE'
    out={'idea_id':idea_id,'status':status,'phases':entries,
         'caveat':'Artifact presence does not establish novelty, external search completeness, or executed MVE support. Phases 17-19 and evidence are separate gates.'}
    return out


# The original bundled ZIP stays byte-for-byte intact. For opt-in CLI execution
# we modify only this project's prepared/extracted runtime, and record a patch
# digest. The vendor's phase prompts, schemas, algorithms and scientific gates
# remain unchanged. Review the resulting scripts/utils.py before live execution.
_SUBSCRIPTION_SHIM = """
# BEGIN RESEARCHLEDGER_SUBSCRIPTION_CLI_SHIM_v1
if os.getenv('RESEARCHLEDGER_V5_PROVIDER') in ('claude', 'codex'):
    def _rl_subscription_init(self, api_key=None, config=None):
        api_cfg = (config or {}).get('api', {})
        self.api_key = None
        self.client = None
        self.model = 'host-default'
        self.max_tokens = api_cfg.get('max_tokens', 8096)
        self.retries = api_cfg.get('retry_attempts', 3)
        self.retry_delay = api_cfg.get('retry_delay_seconds', 5)
        self.json_repair_attempts = api_cfg.get('json_repair_attempts', 2)
        self.call_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def _rl_subscription_ask(self, system, user, temperature=0.3):
        from factory.integrations.subscription_bridge import call_subscription_cli
        answer = call_subscription_cli(os.environ['RESEARCHLEDGER_V5_PROVIDER'],
                                       system=system, user=user, model=None)
        self.call_count += 1
        return answer

    ClaudeClient.__init__ = _rl_subscription_init
    ClaudeClient.ask = _rl_subscription_ask
# END RESEARCHLEDGER_SUBSCRIPTION_CLI_SHIM_v1
"""


def _install_subscription_shim(prepared):
    """Safely install a traceable, project-local Claude/Codex transport shim."""
    path = prepared / 'scripts' / 'utils.py'
    if not path.is_file() or path.is_symlink():
        raise ValueError('prepared V5 scripts/utils.py is missing or unsafe')
    source = path.read_text(encoding='utf-8')
    marker = '# BEGIN RESEARCHLEDGER_SUBSCRIPTION_CLI_SHIM_v1'
    if marker in source:
        if source.count(marker) != 1 or source.count('# END RESEARCHLEDGER_SUBSCRIPTION_CLI_SHIM_v1') != 1:
            raise ValueError('unknown or conflicting V5 subscription shim')
        return
    if 'class ClaudeClient:' not in source or 'def ask_json(' not in source:
        raise ValueError('unsupported V5 version; cannot install subscription shim')
    from factory.io import atomic_text
    atomic_text(path, source.rstrip() + '\n' + _SUBSCRIPTION_SHIM + '\n')
