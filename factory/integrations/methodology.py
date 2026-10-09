"""Bounded ResearchLedger methodology guidance for Paper Factory agents.

Skills are guidance, never authority to claim that a literature search was
performed or that evidence exists. We only inject relevant *Research Method*
steps; skills remain available in full for Claude Code users.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'skills'
STAGE_SKILLS = {
    'idea': ('research-topic-ranking', 'innovation-gap-analysis', 'hypothesis-formulation'),
    'experiment': ('experiment-design', 'baseline-selection', 'ablation-design',
                   'evaluation-protocol', 'reproducible-implementation-spec'),
    'review': ('peer-review-panel', 'pre-submission-editorial-audit'),
}


def brief(stage: str, *, budget: int = 6200) -> str:
    names = STAGE_SKILLS.get(stage)
    if not names:
        raise ValueError(f'unknown methodology stage: {stage}')
    sections = []
    for name in names:
        file = ROOT / name / 'SKILL.md'
        if not file.is_file():
            raise FileNotFoundError(f'missing bundled ResearchLedger skill: {file}')
        text = file.read_text(encoding='utf-8')
        if '## Research Method' not in text:
            raise ValueError(f'Research Method section absent from {name}')
        method = text.split('## Research Method', 1)[1].split('\n## ', 1)[0].strip()
        sections.append(f'### {name}\n{method[:1050]}')
    return ('RESEARCH METHODOLOGY CHECKLIST (instructions, not evidence; never invent studies, '
            'results, citations, baselines or experiment outcomes):\n' +
            '\n\n'.join(sections))[:budget]
