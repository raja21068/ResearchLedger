# Reference Prompts: Literature Review

## Source Prompts (verbatim from ConvFusion)

These are the original module prompts this skill was reorganised from — preserved as
accumulated research intelligence, not as an execution contract. They reference state keys
(`{research_topic}`, `{plans_json}`, …) that no longer exist in v2; read them for the method,
not for a pipeline.

### `modules/discovery/cognition/prompts/extract_problems_prompt.py` — TEMPLATE

```text
You are a research cognition analyst specializing in problem extraction.

Research Topic: {research_topic}

## Papers
{papers_str}

## Papers
{papers_str}

## Papers
{papers_str}

## Papers
{papers_str}

## Extracted Method Families
{extracted_method_families}

## Extracted Innovations
{extracted_innovations}

Synthesize a comprehensive method landscape: method families, dominant approaches, evolution trajectory.

Output JSON:
{{
    "method_landscape": {{
        "method_families": [
            {{
                "name": "method family name",
                "core_idea": "core idea description",
                "strengths": ["strength 1"],
                "weaknesses": ["weakness 1"],
                "representative_papers": ["paper title"],
                "variations": ["variation 1"]
            }}
        ],
        "dominant_approaches": ["approach 1", "approach 2"],
        "evolution_trajectory": "description of how methods have evolved"
    }}
}}

IMPORTANT: Output ONLY raw JSON. No markdown blocks.
```

### `modules/discovery/cognition/prompts/evidence_cognition_prompt.py` — TEMPLATE

```text
You are a research cognition analyst specializing in evidence landscape analysis.

Research Topic: {research_topic}

## Papers
{papers_str}

## Extracted Datasets
{extracted_datasets}

## Extracted Benchmarks
{extracted_benchmarks}

## Extracted Metrics
{extracted_metrics}

Synthesize a comprehensive evidence landscape: datasets, benchmarks, metrics, standard experiments.

Output JSON:
{{
    "evidence_landscape": {{
        "datasets": [
            {{
                "name": "dataset name",
                "description": "dataset description",
                "papers_used_in": ["paper title"],
                "advantages": ["advantage 1"],
                "limitations": ["limitation 1"]
            }}
        ],
        "benchmarks": [
            {{
                "name": "benchmark name",
                "description": "benchmark description",
                "metrics": ["metric 1"],
                "standard_tasks": ["task 1"]
            }}
        ],
        "evaluation_metrics": ["metric 1", "metric 2"],
        "standard_experiments": ["experiment setting 1"]
    }}
}}

IMPORTANT: Output ONLY raw JSON. No markdown blocks.
```
