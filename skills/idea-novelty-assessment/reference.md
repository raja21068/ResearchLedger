# Reference Prompts: Idea Novelty Assessment

## Source Prompts (verbatim from ConvFusion)

These are the original module prompts this skill was reorganised from — preserved as
accumulated research intelligence, not as an execution contract. They reference state keys
(`{research_topic}`, `{plans_json}`, …) that no longer exist in v2; read them for the method,
not for a pipeline.

### `modules/decision/prompts/novelty_evaluator.py` — SYSTEM_PROMPT

```text
Evaluate the novelty of the following research proposal:

Idea:
{idea}

Method:
{method}

Related research context:
- Number of related papers found: {related_papers}
- Research paths: {research_paths}
- Current insights: {current_insights}

Please assess how novel this proposal is compared to existing research. Consider:
1. How different is the approach from existing methods?
2. Does it address a new problem or a new aspect of an existing problem?
3. Are there similar approaches in the literature?
4. Level of innovation and originality
5. Potential to advance the field beyond current state-of-the-art
6. Uniqueness of the proposed methodology

You MUST follow this EXACT JSON schema:
{{
    "novelty_score": 0.6,
    "comparison_with_existing": {{
        "similar_approaches": "existing similar methods",
        "differentiating_factors": "what makes this different",
        "improvements_over_existing": "improvements over current methods"
    }},
    "innovation_level": {{
        "originality": "degree of originality",
        "creative_approach": "creativity of the approach",
        "methodological_innovation": "methodological innovations"
    }},
    "scientific_advancement": {{
        "field_contribution": "contribution to the field",
        "knowledge_gap_filling": "what knowledge gaps it fills",
        "future_research_directions": "potential future directions"
    }},
    "risk_assessment": {{
        "novelty_risks": "risks associated with novelty",
        "validation_challenges": "challenges in validating novelty"
    }},
    "novelty_analysis": "detailed explanation of the novelty assessment"
}}
```

### `modules/conception/prompts/idea_evaluation_prompt.py` — SYSTEM_PROMPT

```text
You are an expert in research evaluation and scientific assessment. Evaluate each of the candidate research ideas based on multiple dimensions:

Research Topic: {research_topic}

1. Novelty (0.0-1.0): How innovative and original is this idea?
2. Feasibility (0.0-1.0): How realistic and implementable is this approach?
3. Scientific Value (0.0-1.0): What is the potential scientific impact?
4. Publication Potential (0.0-1.0): What is the likelihood of publication?
5. Implementation Complexity (0.0-1.0): How complex is the implementation?
6. Overall Score (0.0-1.0): Weighted combination of the above

Candidate Ideas:
{candidate_ideas}

Innovation Opportunities:
{innovation_opportunities}

Research Understanding:
{research_understanding}

Please return the evaluation in JSON format:
{{
    "evaluated_ideas": [
        {{
            "id": "idea_1",
            "title": "brief title",
            "motivation": "motivation",
            "core_innovation": "core innovation",
            "expected_contribution": "expected contribution",
            "technical_direction": "technical direction",
            "novelty": 0.0,
            "feasibility": 0.0,
            "scientific_value": 0.0,
            "publication_potential": 0.0,
            "implementation_complexity": 0.0,
            "overall_score": 0.0,
            "evaluation_rationale": "brief rationale for scores"
        }}
    ]
}}

IMPORTANT REQUIREMENTS:
1. Evaluate ALL provided ideas
2. Provide realistic, well-justified scores
3. Scores should be between 0.0 and 1.0
4. Overall score should be a weighted combination (e.g., novelty=0.3, scientific_value=0.3, feasibility=0.2, publication_potential=0.2)
5. Include clear rationale for the evaluation
6. Consider both strengths and weaknesses of each idea
7. Be critical but constructive in evaluation
```

### `modules/conception/prompts/innovation_state_synthesis_prompt.py` — TEMPLATE

```text
You are an expert in research state synthesis. Your task is to synthesize the Conception module's intermediate results into a unified, structured Innovation State that captures the complete research innovation space for the specific research topic below.

Research Topic: {research_topic}

You have access to the following Conception outputs:
- Research Understanding: The research context and domain analysis
- Domain Challenges: Key challenges and contradictions
- Research Opportunities: Identified innovation opportunities
- Deep Research Gaps: Identified gaps in the research landscape
- Methodological Limitations: Limitations in current approaches
- Innovation Opportunities: High-value innovation directions
- Candidate Ideas: Generated research ideas
- Evaluated Ideas: Assessed research ideas
- Selected Ideas: Selected promising directions
- Final Idea: The chosen final research direction
- Structured Research Ideas: Structured research plans

Please return the Innovation State in JSON format:
{{
  "innovation_state": {{
    "topic_focused_summary": "A concise summary of the innovation space focused specifically for the research topic",
    "candidate_hypotheses": [
      {{
        "hypothesis_id": "hypothesis_1",
        "title": "hypothesis title",
        "description": "detailed description of the hypothesis",
        "novelty": 0.0-1.0,
        "feasibility": 0.0-1.0
      }}
    ],
    "selected_direction": {{
      "idea_id": "idea_1",
      "title": "final idea title",
      "motivation": "research motivation",
      "core_innovation": "core innovation",
      "expected_contribution": "expected contribution",
      "novelty": 0.0-1.0,
      "feasibility": 0.0-1.0,
      "scientific_value": 0.0-1.0,
      "overall_score": 0.0-1.0
    }},
    "novelty_analysis": {{
      "key_novelty_factors": ["factor 1", "factor 2"],
      "comparison_to_sota": "how this idea compares to the state of the art"
    }},
    "feasibility_analysis": {{
      "key_feasibility_factors": ["factor 1", "factor 2"],
      "risk_assessment": "assessment of implementation risks"
    }},
    "innovation_opportunities_summary": "summary of the innovation opportunities landscape",
    "research_gaps_addressed": ["gap 1", "gap 2"],
    "methodological_limitations_addressed": ["limitation 1", "limitation 2"]
  }}
}}

IMPORTANT REQUIREMENTS:
1. CRITICAL: Focus ALL analysis on the specific research topic - exclude irrelevant information
2. Integrate information from all intermediate results to form a comprehensive innovation state
3. Ensure novelty_analysis and feasibility_analysis are based on the evaluated_ideas and selected_ideas
4. candidate_hypotheses should include the key ideas that were most promising
5. selected_direction should be exactly the final_idea with all relevant fields
6. Include all structured research idea details in the selected_direction
7. research_gaps_addressed should reference the gaps from Discovery and deep_research_gaps
8. methodological_limitations_addressed should reference the limitations from Discovery

(JSON formatting policy is provided by Foundation Layer.)
```
