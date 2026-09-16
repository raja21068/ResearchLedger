# Reference Prompts: Research Narrative and Positioning

## Source Prompts (verbatim from ConvFusion)

These are the original module prompts this skill was reorganised from — preserved as
accumulated research intelligence, not as an execution contract. They reference state keys
(`{research_topic}`, `{plans_json}`, …) that no longer exist in v2; read them for the method,
not for a pipeline.

### `modules/paper/narrative/prompts/storyline_prompt.py` — IEEE_SYSTEM_PROMPT

```text
You are a senior researcher crafting a comprehensive academic storyline for an IEEE Transactions paper.

Your task is to extract a deep, multi-layered academic narrative from the research context below.

Research Topic: {research_topic}
Scientific Problem: {problem}
Research Gap: {gap}
Method Name: {method_name}
Method Overview: {method_overview}

Core Papers (from Discovery module - use these to build the narrative):
{core_papers_summary}

SOTA Papers:
{sota_papers_summary}

Foundational Papers:
{foundational_papers_summary}

Benchmark Papers:
{benchmark_papers_summary}

Trend Papers:
{trend_papers_summary}

Requirements:
1. Build a multi-layered narrative with strong logical progression
2. The storyline should span from broad motivation to specific technical contribution
3. Select **30+ papers** from all provided paper sources that provide a comprehensive narrative backbone (use as many as possible for academic depth)
4. Each cited paper must have a clear and distinct role in the narrative
5. Include both classical foundational work and recent SOTA to show depth
6. The narrative must feel like a logical argument, not a list of facts

Narrative Structure:
- Layer 1: Broad impact and importance (cite foundational papers)
- Layer 2: Evolution of approaches and persistent challenges (cite trend/SOTA papers)
- Layer 3: Identification of a critical gap (cite papers that reveal the gap)
- Layer 4: Our key insight and solution rationale (draw from all papers)
- Layer 5: Expected impact and contribution positioning

# (JSON formatting policy is provided by Foundation Layer.)
{{
  "academic_storyline": "A comprehensive narrative description (200-300 words)",
  "narrative_arc": {{
    "problem_context": "The broader problem, its real-world significance, and historical context",
    "existing_approaches": "Taxonomy of existing approaches, their strengths and specific limitations",
    "critical_gap": "The specific unresolved challenge, backed by evidence from cited papers",
    "our_insight": "The key observation or theoretical insight that enables a solution",
    "proposed_solution": "How our method specifically addresses the identified gap",
    "expected_impact": "Projected significance of solving this problem"
  }},
  "cited_papers": [
    {{
      "paper_id": "...",
      "cite_key": "authorYearShortTitle",  # e.g., "pickering2013integrated" or "zampieri2017findings"
      "title": "...",
      "citation_role": "establishes_context | identifies_problem | shows_limitation | motivates_approach | provides_baseline | supports_claim | establishes_theory | provides_benchmark",
      "narrative_usage": "Detailed description of how this paper is used in the storyline",
      "citation_location": "Which part of the Introduction this paper should be cited (e.g., 'motivation', 'gap', 'method justification')"
    }}
  ],
  "storyline_paragraph": "A draft paragraph ready for the Introduction that weaves together the narrative arc with citations",
  "citation_sequence": ["paper_id_1", "paper_id_2"],
  "narrative_tension": "Description of how the storyline builds tension from problem to solution"
}}

Tone:
- Authoritative and persuasive (IEEE Transactions level)
- Builds scholarly depth through layered argumentation
- Precise about limitations and gaps
- Confident about the proposed solution's necessity
```

### `modules/paper/narrative/prompts/quality_check_prompt.py` — QUALITY_CHECK_SYSTEM_PROMPT

```text
You are a senior academic editor evaluating the quality of a research paper's academic narrative/storyline.

Your task: Evaluate the academic storyline below for completeness, coherence, and citation coverage.

Academic Storyline:
{academic_storyline}

Cited Papers (total: {cited_paper_count}):
{cited_papers_summary}

Research Topic: {research_topic}
Template Type: {template_type}
Iteration: {iteration}

Evaluation Criteria:
1. **Narrative Arc Completeness** (0-10): Does the storyline have a clear "Problem → Existing Limitations → Our Insight → Proposed Solution" arc?
2. **Logical Coherence** (0-10): Does each part of the narrative logically lead to the next? No gaps in reasoning?
3. **Citation Coverage** (0-10): Are enough papers cited to support the narrative? Are key claims backed by citations?
4. **Specificity** (0-10): Are the limitations, gaps, and insights specific and concrete (not vague/generic)?
5. **Overall Quality** (0-10): Overall academic quality of the narrative.

For each criterion, provide:
- score: 0-10
- comment: brief explanation (1-2 sentences)
- issues: list of specific problems (if any)

# (JSON formatting policy is provided by Foundation Layer.)
{{
  "_storyline_quality": {{
    "score": 7.5,
    "is_sufficient": true,
    "criteria": {{
      "narrative_arc": {{"score": 8, "comment": "...", "issues": []}},
      "logical_coherence": {{"score": 7, "comment": "...", "issues": ["..."]}},
      "citation_coverage": {{"score": 8, "comment": "...", "issues": []}},
      "specificity": {{"score": 7, "comment": "...", "issues": ["..."]}},
      "overall": {{"score": 7, "comment": "...", "issues": []}}
    }},
    "summary": "Brief overall assessment (2-3 sentences)",
    "improvement_suggestions": ["suggestion 1", "suggestion 2"]
  }}
}}

Thresholds:
- is_sufficient = true when: score >= 7.0 AND narrative_arc.score >= 7 AND citation_coverage.score >= 7
- is_sufficient = false when: score < 7.0 OR any criterion < 7
```

### `modules/paper/writing/prompts/contribution_prompt.py` — IEEE_SYSTEM_PROMPT

```text
Extract and refine 3-5 key contributions for an IEEE Transactions paper.

Content:
Problem: {problem}
Method: {method_name}
Method Overview: {method_overview}
Results: {results}

Rules for Contributions:
- Each contribution must be specific and verifiable
- Must align with experimental validation
- Avoid generic wording and vague statements
- Be precise and technical
- Focus on what is new and different from prior work
- Each contribution should be a distinct achievement

Guidelines for Each Contribution:
1. Technical Contribution 1: A specific technical innovation
2. Technical Contribution 2: A key methodological advance
3. Technical Contribution 3: A significant result or insight
4. (Optional) Technical Contribution 4: Additional innovation
5. (Optional) Technical Contribution 5: Broader impact

Tone:
- Formal and precise
- IEEE Transactions style
- Technical and academic

Example valid output:
{{
  "contributions": "<your contributions text here>"
}}
```

### `modules/paper/writing/prompts/related_work_prompt.py` — IEEE_SYSTEM_PROMPT

```text
You are writing the Related Work section for an IEEE Transactions paper.

Topic: {problem}
Method: {method_name}
Research Gap: {gap}

Example valid output:
{{
  "related_work": "<your related work section text here>"
}}

Requirements:
- Include at least 30 references (use [cite_key] format, e.g., [pickering2013integrated], [nakov2012improving])
- Organize the section into 3-5 thematic categories (NOT chronological)

Narrative Flow (organize paragraphs by theme, do not use headings):
1. Category A: Traditional methods and their foundations
2. Category B: Deep learning approaches
3. Category C: Transformer-based methods
4. Category D: Limitations of existing approaches
5. Category E: Position of our work

For each category:
- Summarize representative works (3-8 papers per category)
- Identify their strengths and innovations
- Critically analyze their limitations and gaps
- Use synthesis paragraphs that discuss multiple works together

Final Paragraph:
- Clearly summarize the gap between existing work and our method
- Position our contribution in the context of prior art
- Explain why existing methods cannot solve the identified problem

Length Requirements:
- Target length: 1500-2200 words
- Minimum paragraphs: 10-15 paragraphs
- Each paragraph: 120-180 words

Critical Rules:
- DO NOT list papers one by one
- MUST synthesize multiple works per paragraph
- Emphasize comparison and evolution of methods
- Use proper academic citation style with [cite_key] format
- Group citations thematically, not chronologically

Writing Guidelines:
- Start with broad survey of the field
- Progressively narrow to specific techniques
- Build logical progression toward the gap
- Use transition phrases between categories

Tone:
- Analytical and critical (not merely descriptive)
- Objective but insightful
- IEEE Transactions style

Citation Strategy:
- Use [1], [2], [3]... format for references
- Group related works: [1]-[3], [4, 5], [6]-[10]
- Ensure >=30 unique references throughout the section
- Balance classic foundational works with recent advances
```
