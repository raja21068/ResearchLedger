# Reference Prompts: Baseline Selection & Comparison Protocol

## Source Prompts (verbatim from ConvFusion)

These are the original module prompts this skill was reorganised from — preserved as
accumulated research intelligence, not as an execution contract. They reference state keys
(`{research_topic}`, `{plans_json}`, …) that no longer exist in v2; read them for the method,
not for a pipeline.

### `modules/experiment/design/prompts/baseline_design_prompt.py` — PROMPT (function-embedded)

```text
You are an expert in research methodology and baseline design.

## Research Topic
{research_topic}

## Experiment Design
{experiment_design.get('experiment_name', 'Experiment')}
Evaluation Metrics: {', '.join(evaluation_metrics) if evaluation_metrics else 'Not specified'}

## Key Papers from Discovery
{_format_key_papers(key_papers)}

---

Your task is to design appropriate baselines and test cases for this experiment.

## Part 1: Baseline Methods
Design 3-5 baseline methods that represent the state-of-the-art or relevant comparisons:

For each baseline, specify:
1. **Name**: Descriptive name of the baseline method
2. **Description**: Brief description of the method
3. **Source**: Which paper or method it's based on
4. **Expected Performance**: Estimated performance on the evaluation metrics
5. **Implementation Notes**: How it could be implemented

## Part 2: Test Cases
Design test cases to validate the experiment:

1. **Standard Test Cases**: Typical scenarios the experiment should handle
2. **Edge Cases**: Boundary conditions and challenging scenarios
3. **Validation Criteria**: How to determine if the experiment is successful

---

Return a JSON object with the following structure:

```json
{{
  "baselines": [
    {{
      "name": "string",
      "description": "string",
      "source": "string",
      "expected_metrics": {{
        "metric1": value1,
        "metric2": value2
      }},
      "implementation_notes": "string"
    }}
  ],
  "test_cases": [
    {{
      "name": "string",
      "description": "string",
      "scenario": "string",
      "expected_outcome": "string",
      "validation_criteria": "string"
    }}
  ]
}}
```

Guidelines:
1. Baselines should be relevant to the research topic and experiment type
2. Expected metrics should be realistic based on literature
3. Test cases should cover both standard and edge scenarios
4. Consider computational feasibility of implementing baselines
5. Include at least one simple baseline for comparison

Return ONLY the JSON object, no extra text or explanation.
```

### `modules/experiment/method/prompts/baseline_requirements_prompt.py` — TEMPLATE

```text
You are an expert ML researcher. Your role is to specify baseline method requirements for a research experiment.

You do NOT generate code. You produce a structured specification that will be handed to a coding system for implementation.

========================
# Research Context
========================

Research Topic: {research_topic}

Experiment Design:
{experiment_design}

========================
# Your Task
========================

Define baseline methods specification. Describe:

1. **Objective**: What comparison should the baselines enable?
2. **Baseline Methods**: List each baseline method with brief description
3. **Comparison Requirements**: How should baselines be compared (same dataset, same metrics, same splits, etc.)
4. **Evaluation Protocol**: How should each baseline be evaluated?

========================
# Output Format
========================

Format your response as a JSON object:
{{
    "baselines": {{
        "objective": "Clear one-sentence description of the comparison goal",
        "baseline_methods": [
            "Method 1: brief description",
            "Method 2: brief description"
        ],
        "comparison_requirements": [
            "same dataset",
            "same evaluation metrics"
        ],
        "evaluation_protocol": [
            "Protocol 1: description",
            "Protocol 2: description"
        ]
    }}
}}

# (JSON formatting policy is provided by Foundation Layer.)
```

### `modules/experiment/prompts/baseline_builder_prompt.py` — TEMPLATE

```text
You are an expert baseline result generator for scientific experiments. Your task has TWO parts:

**Part 1**: Generate simulated baseline results based on core papers from the literature review
**Part 2**: Create test cases that will guide code implementation and verify results against baselines

========================
# Research Context
========================

Research Topic: {research_topic}

Core Papers (from Discovery module):
{core_papers}

Experiment Design:
{experiment_design}

========================
# Part 1: Generate Baseline Results
========================

{full_text_context}

Baseline Methods to simulate:
{baseline_methods}

Evaluation Metrics:
{primary_metric} (primary) + {evaluation_metrics}

For each baseline method, generate results that:
1. Are realistic and consistent with the paper descriptions
2. Follow the expected format of experiment results
3. Include the primary metric and all secondary metrics

========================
# Part 2: Generate Dataset Information
========================

Based on the research topic and core papers, identify key datasets used in this research area.
For each dataset, provide:
1. Dataset name and description
2. Key characteristics (size, domain, language, etc.)
3. Relevant paper references (if available in core papers)
4. How each baseline method typically uses this dataset

Common datasets in this field: {common_datasets}

========================
# Part 3: Create Test Cases
========================

Create Python test cases that verify the implementation can achieve results comparable to these baselines.
These test cases will be used by the coding environment to guide code development.

Each test case should specify:
1. What to test (functionality, metric achievement)
2. Input data format (referencing the datasets above)
3. Expected output threshold compared to baseline
4. How to validate the result

========================
# Output Format
========================

Format your response as a SINGLE JSON object with the following structure:
{{
    "baselines": [
        {{
            "method": "Method name (e.g. BERT-base)",
            "{primary_metric}": 0.0,
            "secondary_metrics": {{
                "metric1": 0.0,
                "metric2": 0.0
            }},
            "paper_id": "OpenAlex ID or paper identifier",
            "paper_title": "Title of the source paper",
            "comment": "Brief note about this baseline result",
            "datasets_used": ["Dataset1", "Dataset2"]  # Which datasets this baseline typically uses
        }}
    ],
    "datasets": [
        {{
            "name": "Dataset name (e.g. LibriSpeech)",
            "description": "Detailed description of the dataset",
            "size": "Number of samples/hours",
            "domain": "Research domain (e.g. speech recognition, NLP)",
            "language": "Primary language(s)",
            "key_characteristics": ["characteristic1", "characteristic2"],
            "paper_references": [
                {{
                    "paper_id": "OpenAlex ID if available",
                    "citation": "Citation text for the dataset paper"
                }}
            ],
            "usage_in_baselines": ["Baseline1", "Baseline2"]  # Which baselines use this dataset
        }}
    ],
    "test_cases": [
        {{
            "test_name": "Descriptive test name",
            "description": "What this test verifies",
            "target_metric": "Name of the primary metric",
            "target_threshold": 0.0,
            "baseline_to_beat": "Method name to compare against",
            "input_data": "Description of required input data (reference datasets above)",
            "expected_output": "Description of expected output format",
            "validation_logic": "Pseudo-code or logic for validation"
        }}
    ],
    "summary": {{
        "strongest_baseline": "Method name of the strongest baseline",
        "performance_gap": "Description of the gap our method should close",
        "test_coverage": "Brief description of what the test cases cover",
        "dataset_coverage": "Summary of datasets used across all baselines"
    }}
}}

IMPORTANT REQUIREMENTS:
1. Generate results for 3-5 baseline methods
2. Metrics must be realistic for the research topic
3. Test cases must be actionable for code generation
4. The primary metric key MUST match the one from experiment design

# (JSON formatting policy is provided by Foundation Layer.)
```
