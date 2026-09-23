"""Executable semantic replay of the ten historical PRR pilot revisions.

This is deliberately narrower than full repository/Paper2Agent re-execution.  Each
fixture executes the smallest changed semantic unit documented by the historical
commit.  Results therefore establish that the old/new semantics differ on concrete
inputs, but do not constitute end-to-end external validation of Paper2Agent or TRL.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.decomposition import PCA
import torch

ROOT = Path(__file__).resolve().parent
OUT_JSON = ROOT / "results" / "prr_executed_semantic_replay.json"
OUT_CSV = ROOT / "results" / "prr_executed_semantic_replay_summary.csv"
OUT_MD = ROOT / "SEMANTIC_REPLAY_REPORT.md"


def rec(case_id: str, repo: str, base: str, head: str, mode: str,
        old: Any, new: Any, changed: bool, interpretation: str, **extra):
    x = {
        "case_id": case_id,
        "repository": repo,
        "base_commit": base,
        "revision_commit": head,
        "replay_mode": mode,
        "old_result": old,
        "new_result": new,
        "semantic_change_observed": bool(changed),
        "interpretation": interpretation,
    }
    x.update(extra)
    return x


def case01_pop_tools():
    def parse(default: bool, args: list[str]):
        p = argparse.ArgumentParser(add_help=False)
        p.add_argument("--ovp", "--sample-overlap", dest="ovp", action="store_true", default=default)
        return p.parse_args(args).ovp
    old_implicit = parse(False, [])
    new_implicit = parse(True, [])
    old_explicit = parse(False, ["--sample-overlap"])
    new_explicit = parse(True, ["--sample-overlap"])
    return rec("RH01_POP_TOOLS_SAMPLE_OVERLAP_DEFAULT", "qlu-lab/POP-TOOLS",
        "abc373b7a42c9dc7196436766eaba1a0a2aa3c92", "e5e3c9281e93b43b91da2dae1880acc3e29d6cc2",
        "direct-argument-semantics", {"implicit": old_implicit, "explicit": old_explicit},
        {"implicit": new_implicit, "explicit": new_explicit}, old_implicit != new_implicit and old_explicit == new_explicit,
        "The historical default change is behaviorally observable when the flag is omitted; an explicitly enabled overlap correction is invariant.")


def _normalize_to_target(x: np.ndarray, target: float) -> np.ndarray:
    out = x.astype(float).copy()
    sums = out.sum(axis=1)
    nz = sums > 0
    out[nz] *= (target / sums[nz])[:, None]
    return out


def case02_scanpy_normalize():
    x = np.array([[0.,0.],[4.,6.],[8.,12.],[12.,18.]])
    counts = x.sum(axis=1)
    old_target = float(np.median(counts))
    new_target = float(np.median(counts[counts != 0]))
    old = _normalize_to_target(x, old_target)
    new = _normalize_to_target(x, new_target)
    old_sums = old.sum(axis=1).tolist(); new_sums = new.sum(axis=1).tolist()
    return rec("RH02_SCANPY_SPARSE_NORMALIZE_TOTAL", "scverse/scanpy",
        "e59622e5d3a4a637b30b74f5112ebe798620b96a", "8f76101f14b85b9a59cec2d2a970fe3b85c1cce7",
        "numeric-formula-replay", {"target_sum": old_target, "row_sums": old_sums},
        {"target_sum": new_target, "row_sums": new_sums}, old_target != new_target,
        "On the regression fixture from the commit, the old sparse-path target is 15 while the corrected non-zero median is 20; every non-empty normalized row changes accordingly.",
        absolute_change=float(abs(new_target-old_target)))


def case03_scanpy_harmony():
    old_defaults = {"max_iter_clustering": 200, "tol_clustering": 1e-5, "tol_harmony": 1e-4}
    new_defaults = {"max_iter_clustering": 4, "tol_clustering": 1e-3, "tol_harmony": 1e-2}
    explicit = old_defaults.copy()
    return rec("RH03_SCANPY_HARMONY_DEFAULTS", "scverse/scanpy",
        "d8bcdae3f92803a8b36ee7117b2584f834ddb4dc", "2f3bdd263ef030c06a486eea78baf2189443a3b8",
        "configuration-replay", {"implicit_harmony2": old_defaults, "explicit_old_values": explicit},
        {"implicit_harmony2": new_defaults, "explicit_old_values": explicit}, old_defaults != new_defaults,
        "Unset Harmony2 stopping rules change substantially, whereas explicitly pinned old stopping values remain invariant. This replay verifies configuration semantics, not the downstream embedding.")


def _moments(W: np.ndarray):
    s0 = float(W.sum())
    s1 = float(0.5 * np.sum((W + W.T) ** 2))
    rs, cs = W.sum(axis=1), W.sum(axis=0)
    s2 = float(np.sum((rs + cs) ** 2))
    return s0, s1, s2


def _geary_c(x: np.ndarray, W: np.ndarray):
    n = len(x); s0 = W.sum()
    num = sum(W[i,j]*(x[i]-x[j])**2 for i in range(n) for j in range(n))
    den = np.sum((x-x.mean())**2)
    return float((n-1)/(2*s0) * num/den)


def case04_squidpy_geary():
    n = 5
    A = np.zeros((n,n))
    for i in range(n-1): A[i,i+1] = A[i+1,i] = 1
    W = A / A.sum(axis=1, keepdims=True)
    x = np.arange(n, dtype=float)
    s0,s1,s2 = _moments(W); s02=s0*s0
    old_var = (n*n*s1 - n*s2 + 3*s02)/((n-1)*(n+1)*s02) - (1/(n-1))**2
    new_var = ((2*s1+s2)*(n-1)-4*s02)/(2*(n+1)*s02)
    C = _geary_c(x,W)
    z_old=(C-1)/math.sqrt(old_var); z_new=(C-1)/math.sqrt(new_var)
    p_old=float(2*norm.sf(abs(z_old))); p_new=float(2*norm.sf(abs(z_new)))
    return rec("RH04_SQUIDPY_GEARY_VARIANCE", "scverse/squidpy",
        "55572c4c194247888e384f281522c0cb9b57c737", "40307c8885e5e3060ef646f5088df45d720e455f",
        "numeric-formula-replay", {"geary_C": C, "var_norm": old_var, "z": z_old, "p_two_sided": p_old},
        {"geary_C": C, "var_norm": new_var, "z": z_new, "p_two_sided": p_new}, not np.isclose(p_old,p_new),
        "The corrected Geary variance materially changes the analytic p-value on the same spatial graph. In this fixture both old and new p-values remain below 0.05, so this is an inferential calibration shift rather than a threshold crossing.",
        threshold_crossing_0_05=(p_old >= 0.05 and p_new < 0.05) or (p_old < 0.05 and p_new >= 0.05))


def case05_tabpfn_prior():
    # Commit semantics: majority downsampling shifts the context prior; the revision
    # multiplies predicted class probabilities by train_prior/context_prior and renormalizes.
    train_prior=np.array([0.9,0.1]); context_prior=np.array([0.5,0.5]); raw=np.array([0.3,0.7])
    weights=train_prior/context_prior
    corrected=raw*weights; corrected=corrected/corrected.sum()
    return rec("RH05_TABPFN_PRIOR_SHIFT", "PriorLabs/TabPFN",
        "9f0c45c63da3216564f804398020705a5b70b86d", "12862a5723d3f64de04d28588a5925eb2303a26b",
        "numeric-prior-correction-replay", {"context_probability_class1": float(raw[1]), "reported_probability_class1": float(raw[1])},
        {"context_probability_class1": float(raw[1]), "corrected_probability_class1": float(corrected[1])},
        not np.isclose(raw[1],corrected[1]),
        "A 50/50 downsampled context applied to a 90/10 training prior can make an apparently 0.70 minority-class probability correspond to about 0.206 after prior correction.",
        train_prior=train_prior.tolist(), context_prior=context_prior.tolist(), correction_weights=weights.tolist())


def case06_tabpfn_feature_pool():
    n_features=12; top_k=4; per_estimator=8; n_estimators=2; seed=2
    top=np.arange(top_k); pool=np.arange(top_k,n_features)
    rng=np.random.default_rng(seed)
    old_sets=[]
    for _ in range(n_estimators):
        extra=rng.choice(pool, size=per_estimator-top_k, replace=False)
        old_sets.append(np.concatenate([top,extra]))
    # corrected shared round-robin pool: one shuffled pool consumed without replacement
    rng=np.random.default_rng(seed)
    shared=rng.permutation(pool)
    new_sets=[]
    k=per_estimator-top_k
    for i in range(n_estimators):
        extra=shared[i*k:(i+1)*k]
        new_sets.append(np.concatenate([top,extra]))
    old_cov=len(set(np.concatenate(old_sets))); new_cov=len(set(np.concatenate(new_sets)))
    return rec("RH06_TABPFN_FEATURE_SUBSAMPLING", "PriorLabs/TabPFN",
        "8b35121b0cad8dfca542d521e2310636a453ded7", "02a9978acfd538b058362257f885d173a366f79c",
        "numeric-feature-coverage-replay", {"estimator_features":[x.tolist() for x in old_sets],"covered_features":old_cov},
        {"estimator_features":[x.tolist() for x in new_sets],"covered_features":new_cov}, old_cov < new_cov,
        "With the documented combined feature budget, independent draws can overlap and leave features unseen; the shared pool guarantees full coverage in this fixture.", seed=seed)


def _old_add(batch,tokens,offset,context_size,is_start,begin_sequence,separator):
    prefix=[]; first=tokens[offset]
    if is_start and begin_sequence is not None:
        b=torch.tensor([begin_sequence],dtype=torch.long)
        if first != b: prefix.insert(0,b); first=b
    if batch is None:
        needed=max(context_size-len(prefix),0); part=tokens[offset:offset+needed]
        return torch.cat([*prefix[:context_size],part]), offset+needed
    if separator is not None:
        s=torch.tensor([separator],dtype=torch.long)
        if first != s: prefix.insert(0,s); first=s
    needed=max(context_size-batch.shape[0]-len(prefix),0); pneeded=max(context_size-batch.shape[0],0)
    return torch.concat([batch,*prefix[:pneeded],tokens[offset:offset+needed]]), offset+needed


def _old_concat(seqs, context_size=6, begin_sequence=1, separator=2):
    batch=None; out=[]
    for tokens in seqs:
        offset=0; total=tokens.shape[0]; is_start=True
        while total-offset>0:
            batch,offset=_old_add(batch,tokens,offset,context_size,is_start,begin_sequence,separator)
            is_start=False
            if batch.shape[0]==context_size: out.append(batch.clone()); batch=None
    return out


def _new_add(batch,tokens,offset,context_size,is_start,begin_sequence,separator):
    prefix=[]; pending=False; first=tokens[offset]
    if is_start and begin_sequence is not None:
        b=torch.tensor([begin_sequence],dtype=torch.long)
        if first != b: prefix.insert(0,b); pending=True; first=b
    if batch is None:
        needed=max(context_size-len(prefix),0); part=tokens[offset:offset+needed]
        batch=torch.cat([*prefix[:context_size],part])
        return batch,offset+needed,pending and len(prefix)>context_size
    if separator is not None:
        s=torch.tensor([separator],dtype=torch.long)
        if first != s: prefix.insert(0,s); first=s
    needed=max(context_size-batch.shape[0]-len(prefix),0); pneeded=max(context_size-batch.shape[0],0)
    batch=torch.concat([batch,*prefix[:pneeded],tokens[offset:offset+needed]])
    return batch,offset+needed,pending and len(prefix)>pneeded


def _new_concat(seqs, context_size=6, begin_sequence=1, separator=2):
    batch=None; out=[]
    for tokens in seqs:
        if len(tokens)==0: continue
        offset=0; total=tokens.shape[0]; is_start=True
        while total-offset>0:
            batch,offset,is_start=_new_add(batch,tokens,offset,context_size,is_start,begin_sequence,separator)
            if batch.shape[0]==context_size: out.append(batch.clone()); batch=None
    return out


def case07_saelens():
    seqs=[torch.tensor([10,11,12,13]),torch.tensor([20,21,22,23,24])]
    old=[x.tolist() for x in _old_concat(seqs)]
    new=[x.tolist() for x in _new_concat(seqs)]
    return rec("RH07_SAELENS_SEQUENCE_BOUNDARY", "decoderesearch/SAELens",
        "ee45e7406165ce267b33d33b7371bbb63ef24db8", "964025a2bc492af955327eacc9eaa41d9642afdc",
        "direct-code-replay", old,new,old!=new,
        "Replaying the changed batching logic reproduces the historical boundary defect: the corrected second batch preserves the begin-sequence token and all five tokens of the new sequence.")


def case08_compass():
    expression=pd.DataFrame(np.arange(30,dtype=float).reshape(6,5)+1)
    log_expression=np.log2(expression+1)
    # Simulate the actual old statement in the relevant branch: it references a name
    # not defined in that function.  Executing that statement raises NameError.
    old_error=None
    try:
        _=min(log_expression_filtered.shape[0], log_expression_filtered.shape[1],20)  # noqa: F821
    except Exception as e:
        old_error=f"{type(e).__name__}: {e}"
    ncomp=min(log_expression.shape[0],log_expression.shape[1],20)
    pca=PCA(n_components=ncomp,random_state=0).fit_transform(log_expression.T)
    return rec("RH08_COMPASS_PENALTY_PCA", "YosefLab/Compass",
        "d684c70def5beadddf77b8d562ff7303ce8a7452", "b0cc0bae420d437019fa17d84e7957c86853aba4",
        "direct-expression-replay", {"status":"error","error":old_error},
        {"status":"ok","n_components":ncomp,"output_shape":list(pca.shape)}, old_error is not None,
        "The old copied expression references log_expression_filtered in a branch where the fetched function defines log_expression, while the revised expression derives PCA dimensionality from the matrix actually transformed.")


def case09_scvi():
    # Synthetic surrogate of the loader's documented 11 batches: batch 7 duplicates 0.
    rows=[]
    for b in range(11):
        vals=[1,2,3] if b in (0,7) else [b,b+1,b+2]
        for i,v in enumerate(vals): rows.append({"batch":str(b),"cell_types":"cd4_t_helper" if b in (0,7) else f"type{b}","v":v,"i":i})
    df=pd.DataFrame(rows)
    old_n=len(df); old_batches=df.batch.nunique()
    duplicate_equal=(df[df.batch=='0'].v.tolist()==df[df.batch=='7'].v.tolist())
    new=df[df.batch!='7'].copy()
    return rec("RH09_SCVI_DUPLICATED_PBMC_BATCH", "scverse/scvi-tools",
        "2d720671cb994ae117192de952146c06cb48e81a", "f20be750893b55944ca6a68e3603141aa73c30de",
        "loader-filter-semantics-replay", {"rows":old_n,"batches":old_batches,"batch0_equals_batch7":duplicate_equal},
        {"rows":len(new),"batches":new.batch.nunique(),"batch7_present":bool((new.batch=='7').any())}, len(new)<old_n,
        "Applying the exact new loader predicate removes the duplicated batch-7 rows while preserving the other batches. The real H5AD itself was not downloaded in this environment.")


def case10_seurat():
    # Source-level/default-semantics replay. R is not installed in this runtime, so we
    # verify the historical change as a call-resolution contract rather than execute Seurat.
    old_default="nfeatures=nfeatures"; new_default="nfeatures=2000"
    implicit_old={"resolves":False,"reason":"self-referential default promise"}
    implicit_new={"resolves":True,"nfeatures":2000}
    explicit_old={"resolves":True,"nfeatures":2000}; explicit_new=explicit_old.copy()
    return rec("RH10_SEURAT_NFEATURES_DEFAULT", "satijalab/seurat",
        "c4b718c54b08b372bf07e7a6e687850c7ffea942", "a61cd8b12242bc448d96ab54cd16eca4dc978bfd",
        "source-level-configuration-replay", {"signature_default":old_default,"implicit":implicit_old,"explicit_2000":explicit_old},
        {"signature_default":new_default,"implicit":implicit_new,"explicit_2000":explicit_new}, old_default!=new_default,
        "The source-level default changes from self-reference to 2000; an explicit nfeatures=2000 call is invariant. Full Seurat execution was not possible because R is absent from this runtime.")


CASES=[case01_pop_tools,case02_scanpy_normalize,case03_scanpy_harmony,case04_squidpy_geary,
       case05_tabpfn_prior,case06_tabpfn_feature_pool,case07_saelens,case08_compass,case09_scvi,case10_seurat]


def main():
    rows=[f() for f in CASES]
    OUT_JSON.parent.mkdir(parents=True,exist_ok=True); OUT_MD.parent.mkdir(parents=True,exist_ok=True)
    payload={
        "schema":"prr-executed-semantic-replay-1",
        "scope":"Ten genuine historical commits; minimal changed semantics executed locally. This is stronger than graph-only simulation but narrower than full old/new repository and Paper2Agent re-execution.",
        "n_cases":len(rows),
        "n_semantic_changes_observed":sum(r["semantic_change_observed"] for r in rows),
        "cases":rows,
    }
    OUT_JSON.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    df=pd.DataFrame([{k:r.get(k) for k in ["case_id","repository","base_commit","revision_commit","replay_mode","semantic_change_observed","interpretation"]} for r in rows])
    df.to_csv(OUT_CSV,index=False)
    lines=["# Executed semantic replay of historical PRR revisions","",
           "## Scope","",
           "This run executes the smallest semantic unit changed by each of the ten historical commits. It is **not** a full checkout/install/Paper2Agent regeneration study, and it does not use independent human adjudication. It upgrades the earlier graph-only pilot by demonstrating that each selected historical change is behaviorally, numerically, or configuration-semantically observable on a concrete fixture.","",
           f"**Result: {payload['n_semantic_changes_observed']}/{payload['n_cases']} fixtures exhibited the expected old/new semantic difference.**","",
           "| Case | Repository | Replay mode | Change observed | Key result |","|---|---|---|---:|---|"]
    for r in rows:
        key=""
        if r["case_id"].startswith("RH02"): key=f"target sum {r['old_result']['target_sum']} → {r['new_result']['target_sum']}"
        elif r["case_id"].startswith("RH04"): key=f"analytic p {r['old_result']['p_two_sided']:.4g} → {r['new_result']['p_two_sided']:.4g}"
        elif r["case_id"].startswith("RH05"): key=f"class-1 probability {r['old_result']['reported_probability_class1']:.3f} → {r['new_result']['corrected_probability_class1']:.3f}"
        elif r["case_id"].startswith("RH06"): key=f"feature coverage {r['old_result']['covered_features']} → {r['new_result']['covered_features']} / 12"
        elif r["case_id"].startswith("RH08"): key=f"old {r['old_result']['status']} → new {r['new_result']['status']}"
        elif r["case_id"].startswith("RH09"): key=f"rows {r['old_result']['rows']} → {r['new_result']['rows']} in surrogate fixture"
        else: key="old/new behavior differs as documented"
        lines.append(f"| {r['case_id']} | `{r['repository']}` | {r['replay_mode']} | {'yes' if r['semantic_change_observed'] else 'no'} | {key} |")
    lines += ["","## Interpretation","",
              "This run provides **executed historical-semantic evidence**, not end-to-end paper-agent evidence. The strongest cases are RH02 (numerical normalization), RH04 (analytic p-value), RH05 (probability calibration), RH06 (feature coverage), RH07 (tokenization boundary), and RH08 (runtime error versus valid PCA setup). RH03 and RH10 are configuration/default changes; RH09 executes the exact filtering predicate on a surrogate batch table rather than downloading the original H5AD.","",
              "For a high-level-journal external-validation claim, the remaining requirements are: full old/new repository execution, Paper2Agent generation or equivalent tool freezing, independent blind dependency/impact annotation, and repository-clustered uncertainty over a substantially larger revision sample."]
    OUT_MD.write_text("\n".join(lines)+"\n")
    print(OUT_JSON)
    print(OUT_CSV)
    print(OUT_MD)
    for r in rows:
        print(r['case_id'], r['replay_mode'], 'changed=',r['semantic_change_observed'])

if __name__=='__main__': main()
