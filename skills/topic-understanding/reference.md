# Reference Prompts: Topic Understanding

## Source Prompts (verbatim from ConvFusion)

These are the original module prompts this skill was reorganised from — preserved as
accumulated research intelligence, not as an execution contract. They reference state keys
(`{research_topic}`, `{plans_json}`, …) that no longer exist in v2; read them for the method,
not for a pipeline.

### `modules/initiation/trigger/prompts/detect_source_prompt.py` — TEMPLATE

```text
You are a research source detection expert. Analyze the user input and determine its source type.

User Input:
{user_input}

Determine the source type from one of the following:
- "paper": Academic paper, preprint, or publication
- "patent": Patent document
- "code": Code repository, implementation, or algorithm
- "dataset": Dataset description or link
- "conversation": Casual conversation, question, or exploratory discussion
- "experiment": Experiment log or results
- "report": Technical report or project report
- "other": Other types

# (JSON formatting policy is provided by Foundation Layer.)

{{
    "source_type": "one of the types above",
    "domain": "the research domain inferred (e.g., Computer Vision, NLP, etc.)",
    "confidence": 0.0-1.0,
    "reasoning": "brief reasoning for your decision"
}}
```

### `modules/initiation/trigger/prompts/extract_content_prompt.py` — TEMPLATE

```text
You are a research content extraction expert. Extract the core research content from the input.

Source Type: {source_type}

Input Content:
{user_input}

Extract the following information:
1. summary: A concise summary of the content (2-3 sentences)
2. problems: Key research problems or challenges mentioned
3. methods: Methods, approaches, or techniques mentioned

# (JSON formatting policy is provided by Foundation Layer.)

{{
    "summary": "concise summary",
    "problems": ["problem1", "problem2"],
    "methods": ["method1", "method2"]
}}
```

### `modules/initiation/trigger/prompts/extract_research_signals_prompt.py` — TEMPLATE

```text
You are a research signal detection expert. Analyze the extracted content and identify research signals.

Summary:
{summary}

Problems:
{problems}

Methods:
{methods}

Identify:
1. limitations: Limitations or gaps in the current work
2. future_work: Potential future research directions mentioned or implied
3. research_signals: Explicit or implicit research signals (trends, opportunities, open questions)

# (JSON formatting policy is provided by Foundation Layer.)

{{
    "limitations": ["limitation1", "limitation2"],
    "future_work": ["future_direction1", "future_direction2"],
    "research_signals": ["signal1", "signal2"]
}}
```

### `modules/initiation/trigger/prompts/build_seed_prompt.py` — TEMPLATE

```text
You are a research seed builder. Consolidate all extracted information into a structured ResearchSeed.

Source Type: {source_type}
Domain: {domain}
Summary: {summary}

Problems:
{problems}

Methods:
{methods}

Limitations:
{limitations}

Future Work:
{future_work}

Research Signals:
{research_signals}

Output a consolidated JSON with all the extracted information.

# (JSON formatting policy is provided by Foundation Layer.)

{{
    "research_seed": {{
        "source_type": "{source_type}",
        "domain": "{domain}",
        "summary": "consolidated summary",
        "problems": ["problem1", "problem2"],
        "methods": ["method1", "method2"],
        "limitations": ["limitation1", "limitation2"],
        "future_work": ["future_direction1", "future_direction2"],
        "research_signals": ["signal1", "signal2"]
    }}
}}
```
