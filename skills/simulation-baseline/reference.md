# Reference Prompts: Simulation-First Results & Baseline Reference

## Source Prompts (verbatim from ConvFusion)

These are the original module prompts this skill was reorganised from — preserved as
accumulated research intelligence, not as an execution contract. They reference state keys
(`{research_topic}`, `{plans_json}`, …) that no longer exist in v2; read them for the method,
not for a pipeline.

### `modules/experiment/simulation/prompts/experiment_simulation_prompt.py` — PROMPT (function-embedded)

```text
You are a scientific research simulation engine for the research topic below.

## Research Topic
{research_topic}

## Experiment Name
{experiment_name}

## Research Question
{research_question or 'Not explicitly specified'}

## Hypothesis
{experiment_hypothesis or 'Not explicitly specified'}

## Evaluation Metrics
{', '.join(evaluation_metrics) if isinstance(evaluation_metrics, list) else str(evaluation_metrics)}

## Datasets
{_stringify_list(datasets_val)}

## Method Specification
{method_spec.get('description', str(method_spec)[:1000]) if isinstance(method_spec, dict) else str(method_spec)[:1000]}

## Baseline Results
{_format_baselines(baselines)}

## Quality Thresholds (if any)
{thresholds_str}

---

Based on the above experiment design, your task is to SIMULATE the expected experimental results. You MUST output a JSON object with the following structure (top-level keys MUST be exactly `simulated_experiment_results` and `simulation_quality`):

```json
{{
  "simulated_experiment_results": {{
    "experiment_name": "{experiment_name}",
    "task_type": "classification|regression|generation|segmentation|detection|other",
    "simulated_metrics": {{
      "{primary_metric}": 0.85
    }},
    "comparison_with_baselines": {{
      "improvement_summary": "Brief description of improvement over baselines",
      "relative_improvement_pct": 3.5
    }},
    "key_findings": [
      "Finding 1",
      "Finding 2"
    ],
    "chart_descriptions": [
      {{
        "title": "Main Result Comparison",
        "type": "bar|line|scatter|heatmap|table",
        "description": "What this chart should show"
      }}
    ],
    "has_metrics": true
  }},
  "simulation_quality": {{
    "confidence": 0.7,
    "quality_notes": "Brief note on confidence justification",
    "risks": ["Potential risk 1"],
    "suggestions": ["Suggestion for improving the experiment"]
  }}
}}
```

Guidelines:
1. Fill in realistic metric values based on the state-of-the-art in this domain.
2. For `simulation_quality.confidence`: 0.0-1.0. Higher when standard benchmarks exist, lower for novel tasks.
3. `has_metrics`: true if quantitative metrics can be reasonably estimated.
4. `key_findings`: 2-5 concise scientific findings.
5. `chart_descriptions`: 1-3 expected charts for the paper.
6. The TOP-LEVEL keys of your JSON MUST be exactly `simulated_experiment_results` and `simulation_quality` — do NOT place `simulated_metrics` or `confidence` at the top level.

Return ONLY the JSON object, no extra text or explanation.
```

### `modules/experiment/simulation/prompts/design_refinement_prompt.py` — PROMPT (function-embedded)

```text
You are an experiment design review assistant for research topic:

## Research Topic
{research_topic}

## Original Experiment Design (v1)
{_format_design(design_v1)}

## Simulated Results
{_format_sim(sim_results)}

## Simulation Quality
Confidence: {sim_quality.get('confidence', 0.5):.2f}
Rationale: {sim_quality.get('rationale', 'Not provided')}

## Baselines
{_format_baselines(baselines)}

---

## Review Criteria

Review the original experiment design against the simulated results. Consider:

1. **Feasibility**: Are the expected metrics realistic given the baselines?
2. **Improvement Margin**: Is the improvement over baselines meaningful (>5%)?
3. **Method Suitability**: Is the chosen method appropriate for the task?
4. **Data Requirements**: Are the required datasets feasible to obtain/use?
5. **Experimental Design**: Are there missing controls or comparisons?

## Refinement Guidelines

If any of these issues are found, propose refinements:

1. **If metrics are too optimistic**:
   - Adjust expected performance to be more realistic
   - Consider alternative evaluation metrics
   - Add more challenging baselines

2. **If improvement margin is small**:
   - Propose method enhancements or variations
   - Suggest hyperparameter tuning ranges
   - Consider ensemble or hybrid approaches

3. **If method is unsuitable**:
   - Recommend alternative methods from literature
   - Suggest architectural modifications
   - Propose different loss functions or training strategies

4. **If data requirements are problematic**:
   - Suggest alternative datasets
   - Propose data augmentation strategies
   - Consider synthetic data generation

5. **If experimental design is incomplete**:
   - Add ablation studies
   - Include more baselines for comparison
   - Add statistical significance tests

---

Return a JSON object with the following structure:

```json
{{
  "refined_experiment_design": {{
    // The refined experiment design (same structure as original)
    "experiment_name": "string",
    "method_spec": {{ ... }},
    "evaluation_metrics": ["..."],
    "datasets": ["..."],
    "quality_thresholds": {{ ... }}
  }},
  "refinement_summary": {{
    "changes_made": true/false,
    "refinement_reason": "Explanation of why refinement was needed",
    "changes_description": [
      "Change 1: description",
      "Change 2: description"
    ],
    "expected_impact": "Expected impact on results"
  }}
}}
```

**Important**: If the original design is adequate (realistic metrics, good improvement margin, suitable method), return it unchanged with `changes_made: false`.

Return ONLY the JSON object, no extra text or explanation.
```

### `modules/experiment/simulation/runtime/path_decision.py` — decision contract (module docstring)

```text
基于仿真质量和实验约束决定后续路径。

    在 experiment_simulation 节点之后调用。

    输入（从 state 读取）:
      - simulated_experiment_results: {"simulated_metrics": {...}, "has_metrics": bool, ...}
      - simulation_quality: {"confidence": float, "quality_notes": str, ...}
      - experiment_assessment: {"needs_dataset": bool, "is_programmable": bool}
      - experiment_design: {"experiment_type": str, ...}

    输出（写入 state）:
      - experiment_path: "offline" | "programmable"
      - simulation_as_oracle: bool
      - programming_required: bool
```

### `modules/experiment/lab_offline/prompts/offline_guidance_prompt.py` — PROMPT (function-embedded)

```text
You are an experiment guidance assistant for offline research experiments.

## Research Topic
{research_topic}

## Experiment Name
{experiment_name}

## Research Objective
{research_objective}

## Method Specification
{method_spec.get('description', str(method_spec)[:1000]) if isinstance(method_spec, dict) else str(method_spec)[:1000]}

## Evaluation Metrics
{', '.join(evaluation_metrics) if isinstance(evaluation_metrics, list) else str(evaluation_metrics)}

## Quality Thresholds
{_format_quality(quality_thresholds)}

## Simulated Expected Results
{sim_metrics if sim_metrics else 'Not available'}

## Expected Key Findings (from simulation)
{chr(10).join(f'- {f}' for f in key_findings[:5]) if key_findings else 'No findings available'}

---

Your task is to generate a detailed offline experiment guidance document. This experiment CANNOT be implemented programmatically and requires human researchers to conduct it offline (e.g., user studies, field research, qualitative analysis, human evaluation).

Generate a JSON object with the following structure to guide the researcher:

```json
{{
  "offline_guidance": {{
    "experiment_name": "{experiment_name}",
    "experiment_type": "user_study | field_study | qualitative | survey | human_evaluation",
    "overview": "Clear description of what the experiment entails and why it must be done offline",
    "preparation": {{
      "materials_needed": ["List of materials, tools, or instruments needed"],
      "participant_requirements": "Required participant profile, sample size, recruitment method",
      "environment_setup": "Physical or virtual environment requirements"
    }},
    "procedure": {{
      "steps": ["Step-by-step instructions for conducting the experiment"],
      "estimated_duration": "Expected time to complete the experiment",
      "ethical_considerations": "Consent forms, privacy, data handling procedures"
    }},
    "required_data": ["List of data points that must be collected"],
    "recommended_instruments": ["Questionnaires, survey forms, observation templates"],
    "analysis_guidance": "How the collected data should be analyzed",
    "expected_outcomes": "What the researcher should expect to observe",
    "quality_criteria": "How to assess whether the experiment was conducted properly"
  }},
  "expected_result_template": {{
    "experiment_name": "{experiment_name}",
    "participants": {{
      "total": 0,
      "demographics": {{}}
    }},
    "data_collection_date": "YYYY-MM-DD",
    "metrics": {{}},
    "key_findings": ["finding 1", "finding 2"],
    "qualitative_observations": "Important observations from the experiment",
    "limitations": ["limitation 1", "limitation 2"],
    "raw_data_location": "Path or reference to raw data files"
  }}
}}
```

Guidelines:
1. Be practical and actionable — the researcher should know exactly what to do
2. Include specific templates for data collection (surveys, observation forms)
3. Reference the simulated expected results as benchmarks for comparison
4. Consider ethical review requirements if applicable
5. Provide realistic time and resource estimates

Return ONLY the JSON object, no extra text or explanation.
```
