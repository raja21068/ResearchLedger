"""V5 final-survivor ELO tournament.

ELO is deliberately downstream of scientific validity. Only ideas that received FINAL GREENLIGHT after the V5 falsification/MVE evidence zone may enter.
"""
from __future__ import annotations
import itertools, json, math
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent))

from utils import load_json, save_json, save_markdown, print_banner, log
from step7_attack_loop import AttackClient

DIMS=("novelty","feasibility","relevance","clarity")


def greenlight_survivors(summary: dict) -> list[dict]:
    """Return only FINAL GREENLIGHT ideas. Works with V5 falsification summaries and legacy V4 attack summaries."""
    out=[]
    for item in summary.get("ideas",[]):
        if item.get("final_decision")=="GREENLIGHT" and isinstance(item.get("final_idea"),dict):
            idea=dict(item["final_idea"])
            idea["_attack_rounds"]=item.get("literature_attack_rounds", item.get("rounds_run",0))
            idea["_falsification_rounds"]=item.get("rounds_run",0) if "mve_evidence_present" in item else 0
            out.append(idea)
    return out


def elo_expected(ra: float, rb: float) -> float:
    return 1.0/(1.0+10.0**((rb-ra)/400.0))


def elo_update(ra: float, rb: float, sa: float, k: float=32.0) -> tuple[float,float]:
    ea=elo_expected(ra,rb); eb=1.0-ea; sb=1.0-sa
    return ra+k*(sa-ea), rb+k*(sb-eb)


def _score_pair(judge: AttackClient, a: dict, b: dict) -> dict:
    system="""You are an independent research-direction judge. Compare two ideas that have ALREADY survived absolute scientific validity checks. Your task is relative ranking only; do not re-greenlight or kill them.

Score each idea 1–10 on exactly four dimensions:
- novelty: intellectual distinctiveness after considering its stated contribution;
- feasibility: realistic execution within a research cycle;
- relevance: importance of the problem to the target field;
- clarity: sufficiently precise to plan experiments now.
Use the full revised ideas, not their titles. Do not reward complexity.
Return ONLY JSON:
{"idea_a":{"novelty":1,"feasibility":1,"relevance":1,"clarity":1,"rationale":"..."},"idea_b":{"novelty":1,"feasibility":1,"relevance":1,"clarity":1,"rationale":"..."},"winner":"A|B|DRAW","reason":"..."}
"""
    out=judge.ask_json(system,json.dumps({"A":a,"B":b},ensure_ascii=False)[:42000],temperature=0.0)
    for side in ("idea_a","idea_b"):
        for d in DIMS:
            try: v=float(out.get(side,{}).get(d))
            except Exception: v=0
            if v<1 or v>10: raise ValueError(f"ELO judge {side}.{d} outside 1..10")
    ca=sum(float(out["idea_a"][d]) for d in DIMS)/4.0
    cb=sum(float(out["idea_b"][d]) for d in DIMS)/4.0
    winner="DRAW" if abs(ca-cb)<1e-9 else ("A" if ca>cb else "B")
    out["winner"]=winner; out["composite_a"]=round(ca,3); out["composite_b"]=round(cb,3)
    return out


def generate_md(data: dict) -> str:
    lines=["# V5 Final-Survivor ELO Tournament\n",f"Generated: {data.get('generated','')}\n",
           "> ELO is a relative ranking layer only. Every entrant already passed literature/reviewer attacks AND the V5 falsification/MVE evidence gate.\n"]
    lines.append("| Rank | Idea | Rating | Mean composite | Attack rounds | Falsification rounds |")
    lines.append("|---:|---|---:|---:|---:|---:|")
    for r in data.get("ranking",[]):
        lines.append(f"| {r.get('rank')} | {r.get('idea_id')} — {r.get('title','')} | {r.get('rating')} | {r.get('mean_composite')} | {r.get('attack_rounds')} | {r.get('falsification_rounds')} |")
    if data.get("matches"):
        lines.append("\n## Pairwise matches\n")
        for m in data["matches"]:
            lines.append(f"- {m['idea_a']} vs {m['idea_b']}: **{m['winner']}** ({m['composite_a']} vs {m['composite_b']})")
    return "\n".join(lines)


def run_survivor_elo(config: dict) -> dict:
    print_banner("STEP 7B: SURVIVOR-ONLY ELO TOURNAMENT")
    out=Path(config["pipeline"]["output_dir"]); ecfg=config.get("survivor_elo",{})
    fpath=out/"falsification_summary.json"
    source=load_json(str(fpath)) if fpath.exists() else load_json(str(out/"attack_loop_summary.json"))
    survivors=greenlight_survivors(source)
    if not ecfg.get("enabled",True):
        data={"generated":datetime.now().isoformat(),"enabled":False,"ranking":[],"matches":[]}; save_json(data,str(out/"survivor_elo.json")); return data
    start=float(ecfg.get("starting_rating",1500)); k=float(ecfg.get("k_factor",32))
    ratings={i.get("idea_id"):start for i in survivors}; scores={i.get("idea_id"):[] for i in survivors}; matches=[]
    if len(survivors)>=2:
        judge=AttackClient(config)
        for a,b in itertools.combinations(survivors,2):
            r=_score_pair(judge,a,b); ia=a.get("idea_id"); ib=b.get("idea_id")
            sa=1.0 if r["winner"]=="A" else (0.0 if r["winner"]=="B" else 0.5)
            ra0,rb0=ratings[ia],ratings[ib]; ra1,rb1=elo_update(ra0,rb0,sa,k)
            ratings[ia],ratings[ib]=ra1,rb1
            scores[ia].append(r["composite_a"]); scores[ib].append(r["composite_b"])
            matches.append({"idea_a":ia,"idea_b":ib,"winner":r["winner"],"composite_a":r["composite_a"],"composite_b":r["composite_b"],"rating_before":{"A":round(ra0,2),"B":round(rb0,2)},"rating_after":{"A":round(ra1,2),"B":round(rb1,2)},"reason":r.get("reason","")})
    ranking=[]
    by_id={x.get("idea_id"):x for x in survivors}
    for iid,rating in ratings.items():
        vals=scores.get(iid,[]); mean=sum(vals)/len(vals) if vals else 0.0
        ranking.append({"idea_id":iid,"title":by_id[iid].get("title",""),"rating":round(rating,2),"mean_composite":round(mean,3),"attack_rounds":by_id[iid].get("_attack_rounds",0),"falsification_rounds":by_id[iid].get("_falsification_rounds",0)})
    ranking.sort(key=lambda x:(x["rating"],x["mean_composite"]),reverse=True)
    for idx,row in enumerate(ranking,1): row["rank"]=idx
    data={"generated":datetime.now().isoformat(),"enabled":True,"policy":{"final_greenlight_only":True,"elo_is_relative_not_validity":True,"ready_for_mve_excluded":True},"starting_rating":start,"k_factor":k,"matches":matches,"ranking":ranking}
    save_json(data,str(out/"survivor_elo.json")); save_markdown(generate_md(data),str(out/"survivor_elo.md"))
    log.info(f"ELO ranked {len(ranking)} FINAL GREENLIGHT survivor(s)")
    return data


if __name__ == "__main__":
    from utils import load_config
    run_survivor_elo(load_config())
