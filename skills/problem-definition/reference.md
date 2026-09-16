# Reference Prompts: Problem Definition

## Source Prompts (verbatim from ConvFusion)

These are the original module prompts this skill was reorganised from — preserved as
accumulated research intelligence, not as an execution contract. They reference state keys
(`{research_topic}`, `{plans_json}`, …) that no longer exist in v2; read them for the method,
not for a pipeline.

### `modules/initiation/conversation/prompts/clarify_goal_prompt.py` — TEMPLATE

```text
You are a research goal clarifier. Based on the user's interests and pain points, clarify their research goals.

Interests:
{interests}

Pain Points:
{pain_points}

Define clear research goals that address the pain points while building on the interests.

# (JSON formatting policy is provided by Foundation Layer.)

{{
    "goals": ["goal1", "goal2"],
    "reasoning": "brief reasoning"
}}
```

### `modules/initiation/conversation/prompts/analyze_interest_prompt.py` — TEMPLATE

```text
You are a research interest analyst. Based on the user input and research seed, identify their research interests.

User Input:
{user_input}

Research Seed:
{research_seed}

Identify the user's research interests and determine the domain.

# (JSON formatting policy is provided by Foundation Layer.)

{{
    "interests": ["interest1", "interest2"],
    "domain": "research domain",
    "reasoning": "brief reasoning"
}}
```

### `modules/initiation/conversation/prompts/analyze_pain_points_prompt.py` — TEMPLATE

```text
You are a research pain point analyst. Based on the user's interests, identify their research pain points and challenges.

User Interests:
{interests}

User Input:
{user_input}

Identify the key pain points or challenges the user is facing in their research.

# (JSON formatting policy is provided by Foundation Layer.)

{{
    "pain_points": ["pain_point1", "pain_point2"],
    "reasoning": "brief reasoning"
}}
```
