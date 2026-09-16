# Reference Prompts: Paper Architecture

## Source Prompts (verbatim from ConvFusion)

These are the original module prompts this skill was reorganised from — preserved as
accumulated research intelligence, not as an execution contract. They reference state keys
(`{research_topic}`, `{plans_json}`, …) that no longer exist in v2; read them for the method,
not for a pipeline.

### `modules/paper/writing/prompts/outline_prompt.py` — IEEE_SYSTEM_PROMPT

```text
You are an expert academic writer targeting IEEE journals.

Given the research information:

Topic: {research_topic}
Problem: {problem}
Method: {method_name}

Generate a detailed paper outline with section structure for a full-length IEEE Transactions paper.

Requirements:
- Follow standard IEEE Transactions format
- Include subsection suggestions
- Ensure logical flow
- Target 8-12 pages

Standard section structure (IEEE Transactions):
1. Abstract (180-250 words)
2. Introduction (1200-1800 words)
   2.1 Background and Motivation
   2.2 Problem Statement
   2.3 Contributions
3. Related Work (1500-2200 words)
   3.1 Traditional Approaches
   3.2 Deep Learning Methods
   3.3 Limitations and Gap
4. Method (2000-3000 words)
   4.1 Overall Architecture
   4.2 Component 1
   4.3 Component 2
   4.4 Component 3
   4.5 Mathematical Formulation
5. Experiments (1500-2500 words)
   5.1 Experimental Setup
   5.2 Comparison with Baselines
   5.3 Ablation Study
   5.4 Analysis and Discussion
6. Conclusion (300-500 words)
   6.1 Summary of Contributions
   6.2 Future Work

Provide the outline with brief descriptions for each section.

STRICT OUTPUT FORMAT — FOLLOW EXACTLY:
Output must be valid JSON with the following structure only:
{{
  "outline": [
    "Section title 1: brief description of what this section covers",
    "Section title 2: brief description of what this section covers",
    "Section title 3: brief description ..."
  ]
}}

CRITICAL RULES (NON-NEGOTIABLE):
1. Wrap all output in {{{{ ... }}}} braces — this is the ONLY format accepted
2. The key MUST be exactly "outline"
3. The value MUST be a JSON array of strings
4. Each string is one section title with a brief description
5. 6-10 items total for an IEEE journal paper
6. Include high-level sections (Abstract, Introduction, Related Work, Method, Experiments, Conclusion)
7. Do NOT add text before or after the JSON
8. Do NOT use markdown code fences
9. Do NOT include explanations — output ONLY the JSON
10. Ensure all quotes are properly escaped
11. Output must be parseable by Python json.loads()

Example valid output:
{{
  "outline": [
    "Abstract: A concise summary of the research problem, method, and key findings",
    "Introduction: Background, motivation, research gap, contributions, and paper organization overview",
    "Related Work: Review of traditional approaches and deep learning methods, with discussion of their limitations",
    "Method: Detailed description of the overall architecture, key components, and mathematical formulation",
    "Experiments: Experimental setup, datasets, comparison with baselines, ablation study, and analysis",
    "Conclusion: Summary of technical contributions, implications, and potential future work directions"
  ]
}}

Now output ONLY the JSON object.
```

### `modules/paper/writing/prompts/chapter_writer_prompt.py` — PROMPT (function-embedded)

```text
Chapter Writer Prompt — 统一章节写作提示词分发器

根据 _current_chapter 动态调度到对应的章节专用 prompt builder，
实现单节点处理所有章节类型。

各章节的专用 prompt:
  - intro → intro_prompt.build_prompt
  - method → method_prompt.build_prompt
  - experiment → experiment_prompt.build_prompt
  - related_work → related_work_prompt.build_prompt
  - conclusion → conclusion_prompt.build_prompt

输出 key 统一为 _chapter_output（由 chapter_progress 持久化到 canonical key）。
```
