from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib
from typing import Iterable
from .docx_inspector import inspect_docx
from .latex_inspector import inspect_latex
from .notebooks import inspect_notebook
from .jats import inspect_jats
from .spreadsheets import inspect_xlsx
ROLE_HINTS={'supplement':'supplement','supporting':'supplement','appendix':'supplement','response':'rebuttal','rebuttal':'rebuttal','reviewer':'reviewer_comments','data':'data','code':'code','script':'code','figure':'figure','table':'table'}
@dataclass
class PackageAudit:
    files:list[dict]; roles:dict[str,list[str]]; warnings:list[str]; total_bytes:int; sha256:str
    def to_dict(self): return asdict(self)
def _sha(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def infer_role(name:str)->str:
    n=name.lower()
    for k,v in ROLE_HINTS.items():
        if k in n:return v
    if Path(name).suffix.lower() in {'.py','.r','.jl','.m','.ipynb'}:return 'code'
    return 'manuscript'
class PackageInspector:
    SUPPORTED={'.docx','.pdf','.md','.txt','.tex','.json','.csv','.xlsx','.ipynb','.xml','.html','.htm','.bib','.ris','.py','.r','.jl','.m'}
    def inspect(self, paths:Iterable[str|Path])->PackageAudit:
        files=[]; roles={}; warnings=[]; total=0; hashes=[]
        for raw in paths:
            p=Path(raw); candidates=[x for x in p.rglob('*') if x.is_file()] if p.is_dir() else [p]
            for fp in candidates:
                ext=fp.suffix.lower(); role=infer_role(fp.name); meta={'path':str(fp),'name':fp.name,'extension':ext,'role':role,'bytes':fp.stat().st_size,'sha256':_sha(fp)}
                total+=meta['bytes']; hashes.append(meta['sha256']); roles.setdefault(role,[]).append(str(fp))
                try:
                    if ext=='.docx':meta['inspection']=inspect_docx(fp)
                    elif ext=='.tex':meta['inspection']=inspect_latex(fp)
                    elif ext=='.ipynb':meta['inspection']=inspect_notebook(fp)
                    elif ext=='.xml':meta['inspection']=inspect_jats(fp)
                    elif ext=='.xlsx':meta['inspection']=inspect_xlsx(fp)
                except Exception as exc:meta['inspection_error']=f'{type(exc).__name__}: {exc}'
                if ext and ext not in self.SUPPORTED:warnings.append(f'Unsupported package file retained as metadata only: {fp.name}')
                files.append(meta)
        package_hash=hashlib.sha256(''.join(sorted(hashes)).encode()).hexdigest()
        if not roles.get('manuscript'):warnings.append('No file inferred as primary manuscript')
        return PackageAudit(files,roles,warnings,total,package_hash)
