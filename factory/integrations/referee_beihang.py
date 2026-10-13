"""Explicit evidence-preserving review/re-review workflow for Beihang Referee.

The vendored Python engine runs with its ORIGINAL core/full prompt, plus an
optional trusted supplemental author-side rubric. Each draft is assessed
independently; earlier concerns feed the revision audit. This command NEVER
edits drafts, issues scientific certifications, or treats model judgments as
confirmed human review. Provider='scripted' is ONLY for engineering tests.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / 'vendor' / '20- Paper Review Agent' / 'Beihang-Referee'
DEFAULT_RUBRIC = ROOT / 'factory' / 'steps' / 'review_assets' / 'senior_review_rubric.txt'
FORMATS = {'.md', '.txt', '.pdf', '.docx', '.tex'}


def _regular_file(raw, *, allowed=None):
    p = Path(raw).expanduser()
    if p.is_symlink():
        raise ValueError(f'symlink file forbidden: {p}')
    p = p.resolve(strict=True)
    if not p.is_file() or (allowed is not None and p.suffix.lower() not in allowed):
        raise ValueError(f'missing/unsupported file: {p}')
    return p


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def review_cycle(project, manuscripts, *, provider='openai-compatible', model=None,
                 pipeline='core', mode='deep', rubric=None, scorecard=False,
                 search_backend=None, fixtures=(), max_rounds=6, timeout=1800,
                 prior_manuscript=None, prior_concerns=None):
    """Review an explicitly supplied draft history with native Beihang Referee.

    No automatic revision: this function intentionally refuses to invent a
    manuscript editor or treat an unreviewed generated edit as a closed defect.
    Each distinct draft is reviewed; repeated file digests are rejected.
    """
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError('project workspace does not exist')
    if not (VENDOR / 'referee' / 'cli.py').is_file():
        raise ValueError('bundled Beihang Referee runtime is missing')
    if pipeline not in {'core', 'full'} or mode not in {'standard', 'deep', 'exhaustive'}:
        raise ValueError('unsupported pipeline or depth')
    if provider not in {'openai-compatible', 'scripted', 'claude', 'codex'}:
        raise ValueError('invalid provider')
    if not isinstance(max_rounds,int) or isinstance(max_rounds,bool) or not 1 <= max_rounds <= 12:
        raise ValueError('max_rounds must be 1..12')
    if not isinstance(timeout,int) or isinstance(timeout,bool) or not 1 <= timeout <= 14400:
        raise ValueError('timeout must be 1..14400')
    papers = [_regular_file(x, allowed=FORMATS) for x in manuscripts]
    if not papers or len(papers) > max_rounds:
        raise ValueError('supply between one and max_rounds distinct manuscript versions')
    paper_hashes = [_sha(x) for x in papers]
    if len(set(paper_hashes)) != len(paper_hashes):
        raise ValueError('re-review requires materially distinct manuscript inputs')
    selected_rubric = _regular_file(rubric or DEFAULT_RUBRIC,allowed={'.txt','.md'})
    if selected_rubric.stat().st_size > 30000 or selected_rubric.stat().st_size == 0:
        raise ValueError('rubric must be a non-empty text file <= 30KB')
    fixtures = list(fixtures or ())
    if provider == 'scripted':
        if len(fixtures) != len(papers):
            raise ValueError('scripted tests need one declared JSON response fixture per draft')
        fixtures = [_regular_file(f, allowed={'.json'}) for f in fixtures]
    elif fixtures:
        raise ValueError('scripted response fixtures are forbidden for live reviews')
    elif provider == 'openai-compatible' and (not (model or os.getenv('REFEREE_MODEL')) or not os.getenv('OPENAI_API_KEY')):
        raise ValueError('OpenAI-compatible review needs model and OPENAI_API_KEY; choose claude or codex for login-based CLI')
    elif provider in {'claude', 'codex'}:
        from factory.integrations.subscription_bridge import cli_status
        availability=cli_status(provider)
        if availability['status'] != 'AVAILABLE':
            raise ValueError(f"{provider} local subscription CLI unavailable: {availability['reason']}")
    if search_backend and search_backend not in {'none','federated','scripted'}:
        raise ValueError('invalid search backend')

    parent = project / 'beihang_referee'
    if parent.is_symlink():
        raise ValueError('unsafe run-directory symlink')
    parent.mkdir(exist_ok=True)
    reports = parent / 'runs'
    reports.mkdir(exist_ok=True)
    tracking=[]
    first_prior = _regular_file(prior_manuscript, allowed=FORMATS) if prior_manuscript else None
    if bool(first_prior) != bool(prior_concerns):
        raise ValueError('initial revision requires prior manuscript AND prior concerns')
    previous = {'prior_concerns':str(_regular_file(prior_concerns,allowed={'.json'}))} if first_prior else None
    for index,(paper, digest) in enumerate(zip(papers,paper_hashes),1):
        args=[sys.executable, '-m','referee.cli','review',str(paper),
              '--provider',provider,'--pipeline',pipeline,'--mode',mode,
              '--run-root',str(reports),'--search-backend',search_backend or ('none' if provider=='scripted' else 'federated'),
              '--rubric-file',str(selected_rubric)]
        if model: args.extend(['--model',model])
        if scorecard: args.append('--scorecard')
        if provider=='scripted': args.extend(['--scripted-responses',str(fixtures[index-1])])
        if previous:
            prior_document = first_prior if index == 1 else papers[index-2]
            args.extend(['--review-mode','revision','--prior-manuscript',str(prior_document)])
            if previous['prior_concerns']:
                args.extend(['--prior-concerns',previous['prior_concerns']])
        env=dict(os.environ)
        env['PYTHONPATH']=str(ROOT)+os.pathsep+str(VENDOR)+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
        try:
            cp=subprocess.run(args,cwd=VENDOR,env=env,capture_output=True,text=True,
                              errors='replace',timeout=timeout,shell=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f'Beihang review round {index} timed out') from exc
        if cp.returncode:
            error=(cp.stderr or cp.stdout)[-1600:]
            for key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY'):
                secret=os.getenv(key)
                if secret: error=error.replace(secret,'[REDACTED]')
            raise ValueError(f'Beihang review round {index} failed: {error}')
        # The vendor prints <run-root>/<run-id>/artifacts/review.md. We validate
        # that this points to a completed run inside the selected workspace.
        output_lines=[s.strip() for s in cp.stdout.splitlines() if s.strip()]
        if not output_lines:raise ValueError('Beihang did not report a review artifact')
        report=Path(output_lines[-1])
        if not report.is_absolute():report=VENDOR / report
        report=report.resolve()
        if not report.is_relative_to(reports.resolve()) or report.name!='review.md' or not report.is_file():
            raise ValueError('Beihang reported a missing or untrusted review artifact')
        run_dir=report.parent.parent
        state_path=run_dir / 'state.json'
        if not state_path.is_file():raise ValueError('Beihang run has no state.json')
        state=json.loads(state_path.read_text(encoding='utf-8'))
        if not state.get('final_review_exportable') or state.get('hard_invariant_failures'):
            raise ValueError('Beihang failed export/invariant gates; cannot mark run successful')
        admitted=state.get('admitted_concerns') or []
        if not isinstance(admitted,list):raise ValueError('invalid admitted concerns schema')
        concerns_file=parent/f'concerns_{digest[:16]}_round_{index:02d}.json'
        concerns_file.write_text(json.dumps(admitted,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        diff_file=None
        if previous:
            prior_document = first_prior if index == 1 else papers[index-2]
            diff_file=parent/f'revision_diff_{digest[:16]}_{index-1:02d}_{index:02d}.json'
            delta=subprocess.run([sys.executable,'-m','referee.cli','compare-revision',
                                  str(prior_document),str(paper),'--json-out',str(diff_file)],
                                   cwd=VENDOR,env=env,capture_output=True,text=True,
                                   errors='replace',timeout=min(timeout,180),shell=False)
            if delta.returncode or not diff_file.is_file():
                raise ValueError('Beihang revision comparison failed')
        closure=state.get('revision_audit',{}).get('scientific_closure') if previous else None
        tracking.append({'round':index,'input':str(paper),'sha256':digest,
                         'review_file':str(report),'run_dir':str(run_dir),
                         'mode':'initial' if index==1 else 'revision',
                         'admitted_major_concerns':len(admitted),
                         'unresolved_issues':len(admitted),
                         'revision_diff':str(diff_file) if diff_file else None,
                         'prior_issues_reverified_by_human':False,
                         'model_revision_closure_audit':closure,
                         'concerns_file':str(concerns_file),
                         'note':'No admitted concerns is not a verified-closed or publication-ready finding.'})
        previous={'prior_concerns':str(concerns_file),'run_dir':str(run_dir)}
    summary={'schema_version':1,'engine':'beihang-referee-0.1.0',
             'native_engine_and_core_prompt_executed':True,
             'trusted_additional_rubric_sha256':hashlib.sha256(selected_rubric.read_text(encoding='utf-8-sig').split('Manuscript begins below:')[0].strip().encode()).hexdigest(),
             'pipeline':pipeline,'depth':mode,'provider':provider,
             'scripted_test_only':provider=='scripted',
             'scientific_peer_review_accuracy_validated':False,
             'author_revisions_generated_automatically':False,
             'independent_human_concern_closure':False,
             'status':'ROUNDS_EXECUTED_NOT_CERTIFIED','rounds':tracking}
    out=parent/f'review_cycle_{paper_hashes[0][:16]}.json'
    out.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return {'status':summary['status'],'rounds':len(tracking),
            'admitted_major_concerns_by_round':[r['admitted_major_concerns'] for r in tracking],
            'native_prompt_plus_user_rubric':True,'scripted_test_only':summary['scripted_test_only'],
            'summary':str(out)}


def review_one(project, manuscript, *, prior_manuscript=None, prior_concerns=None, **kwargs):
    """Single native review, retaining prior concern context when provided.

    Used by the Factory guarded-edit/LaTeX re-review loop.
    """
    result=review_cycle(project,[manuscript],prior_manuscript=prior_manuscript,
                        prior_concerns=prior_concerns, max_rounds=1, **kwargs)
    summary=json.loads(Path(result['summary']).read_text(encoding='utf-8'))
    row=summary['rounds'][0]
    run_dir=Path(row['run_dir'])
    state=json.loads((run_dir/'state.json').read_text(encoding='utf-8'))
    return {'status':state.get('status','UNKNOWN'), 'engine':'beihang-referee-0.1.0',
            'provider':summary['provider'],'scripted_test_only':summary['scripted_test_only'],
            'run_directory':str(run_dir),'review_markdown':row['review_file'],
            'review_exportable':bool(state.get('final_review_exportable')),
            'admitted_major_concerns':len(state.get('admitted_concerns') or []),
            'hard_invariant_failures':len(state.get('hard_invariant_failures') or []),
            'prior_concerns':row['concerns_file'],
            'revision_closure':row['model_revision_closure_audit'],
            'rubric_sha256':summary['trusted_additional_rubric_sha256']}
