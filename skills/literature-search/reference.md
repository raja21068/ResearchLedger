# Reference Prompts: Literature Search

## Source Prompts (verbatim from ConvFusion)

These are the original module prompts this skill was reorganised from — preserved as
accumulated research intelligence, not as an execution contract. They reference state keys
(`{research_topic}`, `{plans_json}`, …) that no longer exist in v2; read them for the method,
not for a pipeline.

### `modules/discovery/retrieval/prompts/query_understanding_prompt.py` — TEMPLATE_ITERATIVE

```text
You are a research query analyst specializing in academic concept extraction.

Research Topic: {research_topic}

This is retrieval round {iteration_num}. Previous rounds already found {num_used_queries} queries.

## Previously Used Queries (AVOID these)
{used_queries_list}

## Task
Based on the above statistics, analyze what aspects of the research topic
are NOT adequately covered by the current paper collection:
1. Missing sub-topics or research domains
2. Missing key keywords or terminology (compare to high-frequency keywords)
3. Missing paradigms, frameworks, or methodological approaches
4. Missing time periods (check year distribution)

Output JSON:
{{
    "coverage_state": {{
        "coverage_score": 0-100,
        "missing_domains": ["domain 1", "domain 2", "..."],
        "missing_keywords": ["keyword 1", "keyword 2", "..."],
        "missing_paradigms": ["paradigm 1", "paradigm 2", "..."],
        "missing_years": ["year range 1", "..."],
        "summary": "brief summary of coverage status"
    }}
}}

IMPORTANT:
- coverage_score: 0-100 (higher = better coverage)
- If all aspects are well-covered, return empty arrays and a high score
- Base your analysis on the statistics above, NOT on memory of the field
- Be honest — if coverage is poor, give a low score and detailed gaps
- Output ONLY raw JSON. No markdown blocks.
```

## Previously Used Queries (DO NOT repeat these or generate similar ones)
{used_queries_list}

Task 1: Expand each core concept into related academic terms that:
- Are real, commonly used terms in the research field
- Are synonyms, subclasses, or closely related terms of the original concept
- Appear frequently in academic papers
- Each term MUST be at most 3 words — longer phrases fail to match papers
- Prioritize terms that were NOT used in previous retrieval rounds

Task 2: Generate 2 focused boolean search queries for OpenAlex that:
- Use OpenAlex boolean syntax: AND, OR, NOT, parentheses, phrase quotes ("")
- Each query targets a DISTINCT research angle from previous rounds
- Queries are concise (at most 2-3 concept groups)
- Use OR to group synonyms/related terms of the same concept
- Use AND to combine different concept categories
- QUALITY over quantity: produce only 2 queries
- MUST be different from ALL previously used queries listed above
- Each individual search term MUST be at most 3 words

Example boolean queries (note: each quoted term is ≤3 words):
- ("sparse coding" OR "dictionary learning") AND (denoising OR "noise reduction")
- ("deep learning" AND "image segmentation") AND (transformer OR CNN)

Output JSON:
{{
    "expanded_queries": [
        "boolean query 1",
        "boolean query 2"
    ],
    "expanded_concepts": {{
        "original_concept_1": ["expanded_term_1", "expanded_term_2", "..."],
        "original_concept_2": ["expanded_term_1", "expanded_term_2", "..."],
        "...": "..."
    }}
}}

IMPORTANT:
- Each individual search term must be ≤3 words (e.g. "image segmentation" OK, "deep learning for medical image segmentation" NOT OK)
- Generate EXACTLY 2 boolean queries, not more
- All expanded terms must be real academic terms
- Queries must use proper OpenAlex boolean syntax
- Use phrase quotes ("") for multi-word terms
- CRITICAL: Your queries must explore NEW angles not covered by previous rounds
- Output ONLY raw JSON. No markdown blocks.
```

### `modules/discovery/retrieval/prompts/query_refinement_prompt.py` — TEMPLATE

```text
You are an academic search query composition specialist for OpenAlex.

Research Topic: {research_topic}
Coverage Gaps: {coverage_state}
Expanded Concepts: {expanded_concepts}

Generate high-quality boolean search queries that fill the coverage gaps using the expanded concepts.

OpenAlex boolean query rules:
- Use AND to combine different concept categories
- Use OR to group synonyms/related terms of the same concept
- Use phrase quotes ("") for multi-word terms
- Use parentheses for grouping
- Each query should combine 2-4 concept groups (not individual terms)
- Keep queries concise and focused
- Generate 2-3 refined queries total, each targeting a specific gap

Example boolean queries:
- ("sparse representation" OR "sparse coding" OR "dictionary learning") AND (denoising OR "noise reduction")
- ("deep learning" AND "image segmentation") AND (transformer OR CNN)
- ("cross-modal" OR multimodal) AND ("sparse representation" AND "noise robust")

Output JSON:
{{
    "refined_queries": ["boolean query 1", "boolean query 2", "boolean query 3", "..."],
    "query_rationale": {{
        "query_1": "Combines [method concept] AND [data concept] AND [evaluation concept] to address gap X",
        "...": "..."
    }},
    "refinement_strategy": "Overall strategy for boolean query composition and gap filling"
}}

IMPORTANT:
- Strictly follow OpenAlex boolean syntax
- 2-4 concept groups per query (each group is an OR of synonyms)
- Use OR within each concept group, AND between concept groups
- Use phrase quotes for multi-word terms
- Output ONLY raw JSON. No markdown blocks.
```

### `modules/discovery/retrieval/prompts/coverage_analysis_prompt.py` — TEMPLATE

```text
You are a search coverage analyst.

Research Topic: {research_topic}
Retrieval Round: {iteration_num}

## Retrieval Statistics
Total Papers: {total_papers}
Year Distribution: {year_distribution}
Top Venues: {top_venues}

## High-Frequency Keywords
{top_keywords}

## Task
Based on the above statistics, analyze what aspects of the research topic
are NOT adequately covered by the current paper collection:
1. Missing sub-topics or research domains
2. Missing key keywords or terminology (compare to high-frequency keywords)
3. Missing paradigms, frameworks, or methodological approaches
4. Missing time periods (check year distribution)

Output JSON:
{{
    "coverage_state": {{
        "coverage_score": 0-100,
        "missing_domains": ["domain 1", "domain 2", "..."],
        "missing_keywords": ["keyword 1", "keyword 2", "..."],
        "missing_paradigms": ["paradigm 1", "paradigm 2", "..."],
        "missing_years": ["year range 1", "..."],
        "summary": "brief summary of coverage status"
    }}
}}

IMPORTANT:
- coverage_score: 0-100 (higher = better coverage)
- If all aspects are well-covered, return empty arrays and a high score
- Base your analysis on the statistics above, NOT on memory of the field
- Be honest — if coverage is poor, give a low score and detailed gaps
- Output ONLY raw JSON. No markdown blocks.
```
