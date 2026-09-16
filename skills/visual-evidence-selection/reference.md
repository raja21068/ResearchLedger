# Reference Prompts: Visual Evidence Selection

## Source Prompts (verbatim from ConvFusion)

These are the original module prompts this skill was reorganised from — preserved as
accumulated research intelligence, not as an execution contract. They reference state keys
(`{research_topic}`, `{plans_json}`, …) that no longer exist in v2; read them for the method,
not for a pipeline.

### `modules/paper/artifacts/prompts/figure_selector_prompt.py` — TEMPLATE

```text
You are an expert academic paper figure curator.

Your job: pick AT MOST {max_figures} figures out of the collected candidates that are the most useful for illustrating the paper's core narrative.

IMPORTANT constraints:
1. At MOST {max_figures} figures can be selected. Pick only the strongest / most distinctive illustrations.
2. AVOID selecting figures that present the SAME information already covered by tables. If a table already shows the main quantitative comparison, prefer a figure illustrating a different angle (e.g., training curves, case study, qualitative comparison, ablation breakdown visualization that the table does not fully convey).
3. Prefer diversity: cover different aspects of the paper if possible (method overview / main comparison / ablation / analysis / qualitative examples).

Paper context
-------------

- Research topic:
{research_topic}

- Experiment section already written (use this to know what figures the text actually references and which narrative is already emphasized):
{experiment_section}

Available figures (candidates)
------------------------------

{figure_list}

Tables already chosen (avoid redundancy with these):
-----------------------------------------------------

{table_list}

# (JSON formatting policy is provided by Foundation Layer.)
Return a JSON with exactly one field:
{{
  "selected_figure_ids": ["figure_id_1", "figure_id_2", ...]
}}

CRITICAL Requirements (MUST follow strictly):
1. The list MUST have EXACTLY BETWEEN 0 AND {max_figures} items. AT MOST {max_figures}. NO EXCEPTIONS.
2. The values MUST be artifact_id strings from the "Available figures" list exactly. Do not invent IDs.
3. Order the list by relevance (most important first).
4. If no figures are suitable, return an empty list.
5. DO NOT include figures whose content is duplicative of the tables above.
6. Return exactly one field: "selected_figure_ids" with the list of IDs.
```
