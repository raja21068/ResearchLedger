"""Generate explicitly scripted vendor-engine fixtures; NO LLM is called."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
common={
 "review_version":"referee-lean-v2",
 "classification":{"field":"methodology","domain":"behavioral science","design":"observational","inference_type":"causal","study_type":"empirical"},
 "manuscript_summary":{"research_question":"Does intervention X improve outcome Y?","approach":"uncontrolled pre-post case series","main_results":"A hypothetical 50 to 60 unit change among 80 observations","claimed_contribution":"descriptive change in Y","developmental_stage":"synthetic demonstration"},
 "minor_concerns":[],"strengths":[],"observations":[],"literature_queries":[],"specialist_requests":[],
 "remaining_uncertainties":[],"overall_scientific_confidence":0.45,
}
verdict={
 "status":"verified","severity":"major","steelman":"The authors may intend a descriptive result, not a causal one.",
 "steelman_survives":True,"steelman_survival_reason":"The highlighted wording still exceeds what the uncontrolled design can establish.",
 "rationale":"The manuscript contains the quoted claim and lacks the required evidence.","confidence":0.92,
 "entailment":{"claim_mapping_valid":True,"anchors_support_failure_mechanism":True,
 "scientific_consequence_proportionate":True,"minimum_resolution_sufficient":True,
 "closure_criterion_testable":True,"steelman_survival_supported":True,"manuscript_contradiction_found":False},
 "uncertainties":[],
}
rounds=[
 ("v1_original.md", "Intervention X causes a 20% improvement in outcome Y.",
  "Causal identification is not established", "An uncontrolled before-after cohort cannot establish a causal intervention effect.",
  "Reframe the result as an observed before-after association; retain the numerical observation without causal interpretation."),
 ("v2_reframed.md", "This observed difference generalizes to all populations.",
  "Unjustified population generalization", "A single convenience cohort cannot support an all-populations generalization.",
  "Limit interpretation to the measured group and describe uncertainty and sampling limits."),
 ("v3_limited.md", "The observed difference is descriptive and limited to the measured cohort.",None,None,None),
]
for i,(filename,quote,title,mechanism,resolution) in enumerate(rounds,1):
 payload={**common,"claims": [{"claim_id":"C001","text":quote,"claim_type":"causal" if i==1 else "interpretive","centrality":"central","scope":"synthetic sample", "proof_burden":["appropriate study design"], "evidence_anchor_ids":["A001"],"support_status":"weak" if i<3 else "descriptive", "confidence":"moderate","alternatives":[]}],
 "evidence_anchors":[{"anchor_id":"A001","source_type":"manuscript","document_id":"D1","locator":"Conclusion","quote_or_fact":quote,"supports":"C001","confidence":"high","url":None,"content_status":None,"content_sha256":None}],
 "candidate_concerns":[],"overall_scientific_confidence":0.4 if i==1 else 0.6 if i==2 else 0.7}
 if title:
  payload["candidate_concerns"]=[{"concern_id":"MC001","title":title,"severity":"major","claim_ids":["C001"],"evidence_anchor_ids":["A001"],"failure_mechanism":mechanism,"scientific_consequence":"The conclusion exceeds the study's design evidence.","minimum_resolution":resolution,"closure_criterion":"Remove unsupported causal or population claims or provide and validate a suitable identification or sampling strategy.","reviewer_confidence":0.9,"external_verification_required":False,"uncertainties":[],"suggested_validation_checks":[]}]
 responses={"lean_core_review":payload}
 if title:
  responses["lean_verify:MC-LEAN-CORE-REVIEWER-0001"]=verdict
 (ROOT/f"scripted_round_{i}.json").write_text(json.dumps(responses,indent=2)+"\n")

papers=[
 """# Demonstration manuscript — version 1\n\nThis is a **synthetic example**, not a human study or measured intervention.\n\n## Methods\nA single hypothetical convenience cohort of 80 participants received intervention X. There was no randomized concurrent control group.\n\n## Results\nThe illustrative mean Y was 50 before and 60 after (20% relative change). No uncertainty estimates or independent replication are available.\n\n## Conclusion\nIntervention X causes a 20% improvement in outcome Y.\n""",
 """# Demonstration manuscript — version 2\n\nThis is a **synthetic example**, not a human study or measured intervention.\n\n## Methods\nA single hypothetical convenience cohort of 80 participants received intervention X. There was no randomized concurrent control group.\n\n## Results\nThe illustrative mean Y was 50 before and 60 after (20% relative change). No uncertainty estimates or independent replication are available.\n\n## Conclusion\nAn observed 20% relative before-after difference in Y is described; causality cannot be established. This observed difference generalizes to all populations.\n""",
 """# Demonstration manuscript — version 3\n\nThis is a **synthetic example**, not a human study or measured intervention.\n\n## Methods\nA single hypothetical convenience cohort of 80 participants received intervention X. There was no randomized concurrent control group and the participants were not randomly sampled.\n\n## Results\nThe illustrative mean Y was 50 before and 60 after (20% relative difference). This is an arithmetic illustration, not an estimate of intervention effectiveness. Confidence intervals, source datasets, and independent replication were not provided.\n\n## Conclusion\nThe observed difference is descriptive and limited to the measured cohort. This single-group example does not support a causal or population-general claim.\n""",
]
for (filename,*_),txt in zip(rounds,papers):
 (ROOT/filename).write_text(txt)
print('Created 3 deliberately scripted referee fixtures and 3 illustrative paper versions.')
