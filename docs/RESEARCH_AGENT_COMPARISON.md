# Research-agent landscape and architectural signature matrix

**Scope:** Publicly documented architectures and repository implementations available by **12 October 2026**. This is a **qualitative capability/signature matrix**, not a benchmark-derived ranking and not a scientific accuracy certification.

The table differentiates **cognitive, operational, epistemic, and institutional autonomy** from research memory, embodied experiments, traceability, reproducibility, implementation transparency, and human governance. Such differentiation prevents conflating idea generation, automation of experiments, validity of conclusions, and institutional verification.

## Operational definitions and key

- **Cognitive**: hypothesis generation, critical reasoning, selection, refinement and research strategy.
- **Operational**: ability to call tools and execute computational/laboratory procedures.
- **Epistemic**: mechanisms for testing evidence, challenging conclusions, checking claim support and preventing unjustified acceptance; **not an empirical measure of actual correctness**.
- **Institutional**: persistent multi-participant coordination, shared scientific records, governance or approval responsibilities; **not simply the number of simulated agents**.
- **Persistent memory**: research state that outlives a single model call or session.
- **Physical experiment**: *Robotics* means automated physical execution; *Human lab* means humans executed agent-designed work; *External lab* means studies occurred outside the agent's autonomous execution loop.
- **Evidence lineage**: the claimed support path from research output to underlying literature, data, experiments or machine-readable provenance. *Idea only* is idea history, not experimental evidence lineage.
- **Reproduction**: what can be re-run or independently verified; *peer repeat*, *isolated repeat*, *code availability*, and *report output* are different levels of support.
- **Prompt disclosure**: *Open* = substantial primary prompts or instruction source visible; *Partial* = excerpts/method descriptions, or important components not fully inspected. Open code does not automatically mean full prompt disclosure.
- **Human gate**: where human oversight occurs (setup, research guidance, experiment execution, protocol approval, manuscript/editorial approval). The existence of optional interaction is not evidence of compulsory human authorization.
- **H/M/L/—**: High / Moderate / Limited / outside primary scope. Qualitative assessment based on documents, **not objective performance levels**. `NR` would indicate not established in public material.

## Large comparative signature matrix

| Category | System | Cognitive | Operational | Epistemic | Institutional | Persistent memory | Physical experiment | Evidence lineage | Reproduction | Prompt disclosure | Human gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Integrated research | [**ResearchLedger + Paper Factory**](https://github.com/raja21068/ResearchLedger) | M | H | M | M | Claim/run ledger | — | H | Isolated repeat | Partial | Protocol/final |
| Integrated research | [AI Scientist (v1)](https://github.com/SakanaAI/AI-Scientist) | H | H | M | L | Run artifacts | — | M | Code/artifacts | Open | Setup |
| Integrated research | [AI Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) | H | H | M | L | Search-tree state | — | M | Code/artifacts | Open | Setup |
| Integrated research | [Google Co-Scientist](https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/) | H | M | M | L | Idea tournament | External lab | M | Proposal-level | Partial | Researcher |
| Integrated research | [Robin](https://github.com/Future-House/robin) | H | H | H | M | Research context | Human lab | M | Code/traces | Partial | Lab execution |
| Integrated research | [A-Lab](https://www.nature.com/articles/s41586-023-06734-w) | M | H | H | M | Lab/active learning | Robotics | M | Methods | Partial | Setup/safety |
| Integrated research | [AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw) | H | H | M | M | Cross-run lessons | — | M | Logs/code | Open | 7 modes |
| Integrated research | [Agent Laboratory](https://github.com/SamuelSchmidgall/AgentLaboratory) | M | H | M | M | Stage artifacts | — | M | Code/reports | Open | Optional |
| Integrated research | [AI-Researcher](https://github.com/HKUDS/AI-Researcher) | H | H | M | L | Global/workflow state | — | M | Code/outputs | Open | Optional |
| Integrated research | [AutoResearch (raja21068)](https://github.com/raja21068/AutoResearch) | H | H | M | M | Cross-run learning | — | M | Code/logs | Open | Optional |
| Evidence & collaboration | [EviGraph](https://arxiv.org/abs/2608.04738) | H | H | H | L | Evidence graph | — | H | Run contracts | Open | Conditional |
| Evidence & collaboration | [Agora](https://arxiv.org/abs/2609.18094) | H | H | H | H | Git/DAG | — | H | Peer repeat | Partial | Setup |
| Computational optimization | [Karpathy autoresearch](https://github.com/karpathy/autoresearch) | M | H | L | L | Git + results TSV | — | M | Rerun code | Open | Setup |
| Idea discovery | [IDEAgent](https://github.com/declare-lab/IDEAgent) | H | M | M | L | Idea lineages | — | Idea only | Idea benchmark | Open | Optional |
| Idea discovery | [ResearchAgent](https://github.com/JinheonBaek/ResearchAgent) | H | M | M | L | Idea history | — | Idea only | Ideas/prompts | Open | Researcher |
| Idea discovery | [EvoScientist](https://github.com/EvoScientist/EvoScientist) | H | H | M | M | Evolving memory | — | M | Code/traces | Partial | On-loop |
| Review & critique | [**Referee Lean v2 (bundled)**](https://github.com/raja21068/ResearchLedger/tree/main/vendor/20-%20Paper%20Review%20Agent/Referee-Lean-v2) | M | M | H | M | Review records | — | H | Eval protocols | Open | Editor |
| Review & critique | [ReviewGrounder](https://github.com/EigenTom/ReviewGrounder) | M | M | H | L | Review context | — | M | ReviewBench | Open | Editor |
| Review & critique | [DeepReviewer 2.0](https://github.com/ResearAI/DeepReviewer-v2) | M | M | M | L | Job artifacts | — | M | PDF reports | Partial | Editor |
| Review & critique | [AgentReview](https://github.com/Ahren09/AgentReview) | M | M | M | M | Review dialogues | — | M | Review simulation | Open | Simulated |
| Review & critique | [OpenReviewer](https://github.com/maxidl/openreviewer) | M | L | M | L | Review outputs | — | L | Model/demo | Open | Editor |
| Paper-to-agent/code | [Paper2Agent](https://github.com/jmiao24/Paper2Agent) | M | H | M | L | Agent/tool assets | — | M | Runnable tools | Open | Operator |
| Paper-to-agent/code | [Paper2Code / PaperCoder](https://github.com/going-doer/Paper2Code) | M | H | M | L | Generated code | — | M | Code repo | Open | Operator |
| Writing & presentation | [PaperOrchestra](https://github.com/google-research/paper-orchestra) | M | H | M | L | Draft artifacts | — | M | Manuscript | Open | Author |

### Coding restrictions and interpretation

1. **Architecture is not achievement.** An `H` in epistemic autonomy indicates a substantial reported verification mechanism, **not** that the system is more scientifically accurate than a system marked `M`.
2. **Do not treat missing scope as a deficiency.** Paper2Code and ReviewGrounder do not aim to design physical experiments. Their `—` entries are intentional rather than weaknesses.
3. **Physical-execution distinctions matter.** Robin's reported wet-lab experiments were **performed by humans** using the system's proposals and analyses. A-Lab executed real synthesis through laboratory robotics. Google Co-Scientist collaborated with external researchers; that does not mean it autonomously operated lab equipment.
4. **Agora vs EviGraph are different:** Agora's graph is a **shared contribution DAG with independently posted verification records**; EviGraph's graph is a **typed claim–hypothesis–experiment–finding evidence control state**. Neither should be presented as equivalent to independently proven scientific truth.
5. **ResearchLedger is a suite, not a single monolithic model.** ResearchLedger includes (a) Factory stages for idea generation, draft/review, sandbox execution and revision, (b) an independent claims/evidence/run ledger, (c) a vendored **Referee Lean v2** with 24 reviewer-role definitions, and (d) a bundled **Idea Discovery v5 ZIP** at `vendor/idea-generation/idea-discovery-v5.zip`. The bundled archives and stand-alone capabilities **must not be equated to components verified as automatically running in Factory's default workflow**. The Idea Discovery v5 ZIP's internal behavior has not been inspected for this matrix. Referee appears separately to make the category comparison fair; its presence does not represent a separately benchmarked performance improvement by ResearchLedger.
6. **ResearchLedger reproduction is bounded.** Its validation mode performs an **isolated repeat** and integrity checks; this does **not** independently reproduce the result through a second scientific implementation or validate all inferential claims. DOI resolution verifies bibliographic metadata, not the truth of cited claims.
7. **A-Lab correction:** Use the updated Nature article (which has a 2026 author correction) when reporting synthesis success numbers. The matrix intentionally omits disputed point estimates.
8. **Independent validation is not implied.** Published benchmarks and author reports have different tasks, evaluators, budgets and definitions; cross-system rankings require common-task testing.

## Interpretation by architectural family

| Family | What it principally advances | ResearchLedger comparison |
|---|---|---|
| Generative and computational autonomy | Hypotheses, code, iteration, manuscripts | Paper Factory spans these stages but has narrower exploration and benchmarking evidence than some specialist systems |
| Physical laboratory autonomy | Closing the loop with real laboratory data | ResearchLedger records computational runs; no native autonomous robotic laboratory is demonstrated |
| Evidence-guided autonomy | Claims, experimental provenance and correction | ResearchLedger's claim/run ledger is its principal differentiator; EviGraph also offers explicit evidence dependencies |
| Institutional / collective science | Shared histories, verification, collaboration | Agora has an explicit shared Git/DAG for independent contributors; ResearchLedger's provenance is currently predominantly project-local |
| Idea-generation specialists | Quality-diversity ideation, literature-grounded novelty | ResearchLedger's active Factory S1 enforces falsifiability; Idea Discovery v5 is bundled but not evaluated internally here |
| Peer-review specialists | Paper-specific critiques, verification and revision | Bundled Referee has broader documented mechanisms than default Factory review; ReviewGrounder has independent publication-level benchmark evaluation |
| Paper-to-agent and paper-to-code | Making existing papers interactive or executable | Different output goals from novel-science orchestration; ResearchLedger does not natively duplicate these workflows |
| Manuscript-production specialists | Structure, scholarly synthesis, figures, writing | ResearchLedger can generate and revise papers, but PaperOrchestra explicitly specializes in manuscript production |

## Primary sources

- ResearchLedger code and limitations: https://github.com/raja21068/ResearchLedger ; https://github.com/raja21068/ResearchLedger/blob/main/docs/SCIENTIFIC_READINESS.md ; https://github.com/raja21068/ResearchLedger/blob/main/README.md
- Google Co-Scientist: https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/
- The AI Scientist-v2: https://github.com/SakanaAI/AI-Scientist-v2
- Robin: https://www.futurehouse.org/research/demonstrating-end-to-end-scientific-discovery-with-robin-a-multi-agent-system
- A-Lab: https://www.nature.com/articles/s41586-023-06734-w
- EviGraph: https://arxiv.org/abs/2608.04738
- Agora: https://arxiv.org/abs/2609.18094
- AutoResearchClaw: https://arxiv.org/abs/2605.20025
- Agent Laboratory: https://aclanthology.org/2025.findings-emnlp.320/
- IDEAgent: https://arxiv.org/abs/2607.22375
- ResearchAgent: https://aclanthology.org/2025.naacl-long.342/
- ReviewGrounder: https://aclanthology.org/2026.acl-long.1477/
- AgentReview: https://aclanthology.org/2024.emnlp-main.70/
- Paper2Agent: https://www.nature.com/articles/s41586-026-11044-y
- Paper2Code/PaperCoder: https://github.com/going-doer/Paper2Code
- PaperOrchestra: https://arxiv.org/abs/2604.05018
- Karpathy autoresearch: https://github.com/karpathy/autoresearch
- DeepReviewer: https://github.com/ResearAI/DeepReviewer-v2
- EvoScientist: https://github.com/EvoScientist/EvoScientist

**Suggested manuscript caption:** *Table 12. Architectural signatures of autonomous scientific research systems as of October 2026. H/M/L denote high/moderate/limited documented capability relative to a predeclared functional rubric, not empirically measured performance. Physical experiments and reproducibility mechanisms are distinguished by implementation modality and evidential status. ResearchLedger encompasses distinct bundled components; its main Factory workflow does not by default invoke every feature of the bundled specialist engines.*


## Related research

[Kumar et al., *AutoResearch: An Execution-Grounded Multi-Agent Framework for Reliable Research Workflow Automation* (arXiv:2607.02520)](https://arxiv.org/abs/2607.02520) describes the [separate AutoResearch project](https://github.com/raja21068/AutoResearch). The preprint does not independently validate ResearchLedger.
