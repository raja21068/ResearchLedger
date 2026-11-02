# How the user raises paper quality — and what ResearchLedger now does about it

Source: the user's Claude memory export, the memories of 13 paper projects under `~/.claude/projects/`
(Paper Factory, VeriMID, TrustFed, AgentForge, VisGen/SlideGen, Lagun validation, LLM-Chemistry, pFedLLM, NFNF-DGCL,
SODA-Track, JPS, HINTS-JCHI, CausalTinyIoT) and 333 of the user's own prompts in those sessions (Jul–Nov 2026).

## 1. What the user actually does, round after round

| Habit (their words) | How often | Where |
|---|---|---|
| Paste a senior-reviewer report from ChatGPT → "fix it in loop, don't ask, make a plan, task by task" | every revision | VeriMID, TrustFed, JPS, Zeng, NFNF |
| "Think more, don't follow all suggestions, just the important ones" | often | TrustFed, VeriMID |
| "Score again" / "why is the score low?" / "make it at least 8.0" — targets quality 8.0, impact 9.0, novelty 8.3, methods 8.3, readiness 7.3 | every paper | Paper Factory, pFedLLM, SlideGen |
| "Same writing style, same length, same template as this example paper; extra material to the supplement" | every new paper | SODA-Track, TrustFed, Zeng |
| Page budget ("11–12 pages, 17 is too much") and reference target ("40 citations") | often | TrustFed, NFNF, ADHD |
| Figures "look AI generated / ugly / misaligned" → redraw for a rank-1 journal, vector, labels inside bounds | very often | 8 projects |
| "Fill all tables", "why results missing", compare against baselines, "why is ours better", "bold ours" | every results phase | AgentForge, VeriMID, TrustFed |
| Always run the reviewer simulation + idea stress test before code; stop before code so they check paper and data | standing rule | Paper Factory |
| Humanize at the end (`human` skill, `my-writing-style`) | final pass | ADHD, SODA-Track |
| "Which journal?" | new papers | ADHD, Lagun |

## 2. What actually hurt quality (from the project memories)

1. **Untraceable or fabricated numbers sink papers.** AgentForge was rejected (gold-patch leakage, uncontrolled
   baselines; the 40% result could not have come from the code). VisGen's tables could not be traced to any run
   and an ablation was once labelled "Hypothetical". The fix that worked everywhere: *tables generated from run
   records, a script that re-derives every number in the text and fails on mismatch* (Lagun `26_verify_manuscript_numbers.py`
   caught two real errors).
2. **Response letters that promise work that was never done** (VisGen: a 500-pair dataset, kappa 0.85, a human study).
3. **Editing alone stops raising scores.** Paper Factory, 3 hand-run review→fix rounds on a draft: methods 3.9→6.2,
   readiness 5.4→6.8, but novelty stuck near 5 and impact near 7; gains shrank 1.10 → 0.24. The remaining gap needed
   new experiments, not new wording.
4. **Construct and leakage errors** (Lagun: variables were not what their names said; a survival-code leak gave
   C-index 0.29–0.39; per-script test splits differed).
5. **AI-looking figures**: in-figure titles, banners, rainbow boxes, decorative fake data, labels out of bounds.

## 3. What ResearchLedger now does (this build)

| Lever | Implementation |
|---|---|
| Score with the user's own targets | Review → fix loop scores quality / impact / novelty / methods / readiness (Referee-Lean 1–10 anchors). Default targets 8.0 / 9.0 / 8.3 / 8.3 / 7.3, editable per loop. |
| "Don't follow all suggestions" | The plan move triages every concern: `text_fix`, `new_analysis`, `new_experiment`, `reject` (with reason). Only text fixes and analyses of existing results are applied; experiments go to a list for the user. |
| Stop when editing stops helping | Plateau: mean score gain < 0.3 → stop and say plainly which concerns need experiments (lesson 3). |
| No untraceable numbers | **Submission gate**: every number in tables and the abstract is matched against `results/*.json`; a fix that *introduces* a number found in no result file is rejected and redone. |
| No empty promises | A concern marked resolved must quote text that really exists in the revised `.tex`. |
| Example paper style and length | Optional example PDF: pages, words, figures, tables and references are measured and compared with the manuscript (±20%). |
| Page and citation budget | Gate checks page count against the target and cited references against the target (default 40); cited keys missing from the `.bib`, uncited entries, and every DOI/arXiv id looked up at Crossref/arXiv. |
| Figures | Gate lists raster figures and low-resolution images (vector PDF preferred) and missing figure files. |
| Leftover placeholders | `\PFVAL`, `\pending`, TBD, `[CITATION NEEDED]`, `??` are listed with line numbers. |
| Overclaiming | "first", "novel", "state-of-the-art", "significantly" (with no test or interval in the paper), "prove", "guarantee" are listed for calibration. |

## 4. On "show only the strong part"

The system helps present strengths: lead with the strongest result, move secondary tables to the supplement with a
pointer, report what the method is best at. It will not delete a comparison or a row so that "ours" becomes bold,
and it will not drop a negative result that changes the conclusion: reviewers re-check this (AgentForge was rejected
for exactly this class of problem), and a supplement with the full table protects the paper. Negative findings can
be shortened and framed as scope or boundary conditions (the user's own choice on VeriMID: "keep it but soften").
