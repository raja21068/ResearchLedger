"""Live Crossref DOI *metadata* verification and explicit nearest-prior-art register.

Never represents DOI resolution as validation of paper claims or novelty. Network
access happens only on explicit operator request (`researchctl literature verify`).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from factory.io import atomic_json

DOI_RE = re.compile(r'^10\.[0-9]{4,9}/[-._;()/:A-Z0-9]+$', re.I)
REGISTRY = '_inputs/literature.json'
PRIOR_ART = '_inputs/prior_art.json'
DOI_RECEIPTS = 'control/doi_verifications'


def normalize_doi(value):
    doi = str(value).strip()
    doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi, flags=re.I)
    doi = re.sub(r'^doi:\s*', '', doi, flags=re.I)
    if not DOI_RE.fullmatch(doi) or len(doi) > 240:
        raise ValueError('invalid DOI syntax')
    return doi.lower()


def _read(path, fallback):
    if path.is_symlink():
        raise ValueError(f'unsafe symlink: {path}')
    if not path.exists():
        return fallback
    if path.stat().st_size > 1_000_000:
        raise ValueError('literature registry exceeds 1 MB')
    return json.loads(path.read_text(encoding='utf-8'))


def _digest(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def _receipt_path(project, doi):
    return Path(project) / DOI_RECEIPTS / (hashlib.sha256(doi.encode('utf-8')).hexdigest() + '.json')


def verify_doi(project, doi, *, fetch=None):
    doi = normalize_doi(doi)
    project = Path(project).resolve()
    url = 'https://api.crossref.org/works/' + quote(doi, safe='')
    if fetch is None:
        def fetch(target):
            req = Request(target, headers={'User-Agent': 'PaperFactoryResearchLedger/2.0 (metadata verification)'})
            with urlopen(req, timeout=12) as response:
                if response.status != 200:
                    raise ValueError('Crossref returned non-200 HTTP status')
                raw = response.read(512_001)
                if len(raw) > 512_000:
                    raise ValueError('Crossref response too large')
                return json.loads(raw)
    try:
        payload = fetch(url)
    except (OSError, TimeoutError) as exc:
        raise ValueError(f'Crossref lookup unavailable: {exc}') from exc
    message = payload.get('message') if isinstance(payload, dict) else None
    if not isinstance(message, dict) or normalize_doi(message.get('DOI', '')) != doi:
        raise ValueError('Crossref DOI response does not match the requested DOI')
    title = message.get('title', [])
    title = title[0] if isinstance(title, list) and title else ''
    if not isinstance(title, str) or not title.strip():
        raise ValueError('Crossref returned no title')
    published = message.get('published', message.get('issued', {}))
    try:
        year = int(published['date-parts'][0][0])
    except (KeyError, IndexError, TypeError, ValueError):
        year = None
    registry_path = project / REGISTRY
    registry = _read(registry_path, {'schema_version': 1, 'works': []})
    if not isinstance(registry, dict) or not isinstance(registry.get('works'), list):
        raise ValueError('invalid literature registry')
    if any(not isinstance(item, dict) for item in registry['works']):
        raise ValueError('literature registry contains a non-object entry')
    previous = [item for item in registry['works'] if item.get('doi') != doi]
    container_titles = message.get('container-title')
    container_title = (container_titles[0] if isinstance(container_titles, list) and
                       container_titles and isinstance(container_titles[0], str) else '')
    previous.append({'doi': doi, 'title': title.strip(), 'year': year,
                     'container_title': container_title,
                     'metadata_status': 'CROSSREF_RESOLVED',
                     'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                     'scope': 'BIBLIOGRAPHIC_METADATA_ONLY_NOT_FINDING_VALIDATION'})
    registry['works'] = sorted(previous, key=lambda item: item['doi'])
    row = next(work for work in registry['works'] if work['doi'] == doi)
    # A separate receipt catches accidental/unauthorized registry-only edits.
    # It is NOT an independently signed response from Crossref.
    atomic_json(_receipt_path(project, doi),
                {'doi': doi, 'registry_entry_sha256': _digest(row),
                 'crossref_response_sha256': _digest(payload),
                 'scope': 'CROSSREF_METADATA_ONLY', 'checked_at_utc': row['checked_at_utc']})
    atomic_json(registry_path, registry)
    return row


def scaffold_prior_art(project):
    dest = Path(project) / PRIOR_ART
    if dest.exists() or dest.is_symlink():
        raise ValueError('prior_art.json already exists; edit it')
    atomic_json(dest, {'schema_version': 1, 'nearest_prior_art': [],
                      'novelty_claim': '', 'researcher_acknowledgement': False})
    return {'path': str(dest), 'status': 'NEEDS_OPERATOR_INPUT'}


def audit(project):
    project = Path(project).resolve()
    try:
        registry = _read(project / REGISTRY, {'works': []})
        prior = _read(project / PRIOR_ART, {'nearest_prior_art': []})
        problems = []
        works = registry.get('works') if isinstance(registry, dict) else None
        if not isinstance(works, list):
            raise ValueError('literature.works must be a list')
        vetted = set()
        for work in works:
            if not isinstance(work, dict):
                problems.append('non-object literature record')
                continue
            try:
                doi = normalize_doi(work.get('doi', ''))
                if work.get('metadata_status') != 'CROSSREF_RESOLVED' or not work.get('title'):
                    problems.append(f'{doi}: DOI metadata not verified')
                else:
                    receipt = _read(_receipt_path(project, doi), {})
                    if (not isinstance(receipt, dict) or
                            receipt.get('doi') != doi or
                            receipt.get('registry_entry_sha256') != _digest(work) or
                            receipt.get('scope') != 'CROSSREF_METADATA_ONLY'):
                        problems.append(f'{doi}: Crossref verification receipt missing or stale')
                    else:
                        vetted.add(doi)
            except ValueError:
                problems.append('invalid DOI in literature registry')
        if not vetted:
            problems.append('no externally resolved DOI metadata recorded')
        art = prior.get('nearest_prior_art') if isinstance(prior, dict) else None
        if not isinstance(art, list) or not art:
            problems.append('nearest_prior_art missing')
        else:
            for item in art:
                if not isinstance(item, dict):
                    problems.append('invalid nearest prior art entry')
                    continue
                try:
                    doi = normalize_doi(item.get('doi', ''))
                except ValueError:
                    problems.append('invalid nearest prior art DOI')
                    continue
                if doi not in vetted:
                    problems.append(f'{doi}: nearest prior art not in verified DOI registry')
                for field in ('overlap', 'difference', 'limitation'):
                    if len(str(item.get(field, '')).strip()) < 15:
                        problems.append(f'{doi}: document {field} in at least 15 characters')
        if not isinstance(prior, dict) or len(str(prior.get('novelty_claim', '')).strip()) < 15:
            problems.append('novelty_claim needs a specific, testable contribution description')
        if not isinstance(prior, dict) or prior.get('researcher_acknowledgement') is not True:
            problems.append('researcher must review the nearest-prior-art matrix')
        return {'status': 'PASS' if not problems else 'BLOCKED',
                'verified_dois': len(vetted), 'issues': problems,
                'limitations': ['Crossref verifies metadata only, not novelty, experimental findings, or correctness.',
                                'A manually supplied prior-art comparison is not an exhaustive literature search.']}
    except (ValueError, OSError, TypeError, KeyError) as exc:
        return {'status': 'BLOCKED', 'verified_dois': 0, 'issues': [str(exc)]}
