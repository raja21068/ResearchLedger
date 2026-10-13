"""Validate user-supplied run options before any expensive model calls."""
from __future__ import annotations

import math
from pathlib import Path

COUNTS = {"review_max_rounds": (1, 20), "review_min_scored_dimensions": (1, 49),
          "idea_count": (1, 30), "code_run_attempts": (1, 20),
          "code_timeout": (60, 14400), "writer_timeout": (60, 14400)}
VALID_CODE_MODES = {"agent", "pipeline"}
VALID_REVIEW_AGENTS = {"auto", "light", "referee-full", "referee-native", "beihang-native"}


def validate_context(context):
    if not isinstance(context, dict):
        raise ValueError("context.json must be a JSON object")
    for key, (low, high) in COUNTS.items():
        if key in context:
            value = context[key]
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f"{key} must be an integer from {low} to {high}")
    if context.get("code_mode", "agent") not in VALID_CODE_MODES:
        raise ValueError("code_mode must be 'agent' or 'pipeline'")
    if context.get("writer_provider", "claude") not in ("claude", "codex"):
        raise ValueError("writer_provider must be claude or codex")
    if context.get("review_agent", "auto") not in VALID_REVIEW_AGENTS:
        raise ValueError("review_agent must be auto, light, referee-full, referee-native, or beihang-native")
    if context.get('referee_provider','openai-compatible') not in {'openai-compatible','claude','codex'}:
        raise ValueError('referee_provider must be openai-compatible, claude, or codex')
    if context.get('referee_pipeline', 'core') not in {'core', 'full'}:
        raise ValueError('referee_pipeline must be core or full')
    if context.get('referee_mode', 'deep') not in {'standard', 'deep', 'exhaustive'}:
        raise ValueError('referee_mode must be standard, deep or exhaustive')
    if context.get('referee_search_backend', 'federated') not in {'federated','none','scripted'}:
        raise ValueError('referee_search_backend must be federated, none or scripted')
    if 'referee_scorecard' in context and not isinstance(context['referee_scorecard'], bool):
        raise ValueError('referee_scorecard must be boolean')
    if 'referee_rubric' in context and (not isinstance(context['referee_rubric'], str) or not context['referee_rubric'].strip()):
        raise ValueError('referee_rubric must be a non-empty text-file path')
    if "allow_network_install" in context and not isinstance(context["allow_network_install"], bool):
        raise ValueError("allow_network_install must be true or false")
    if "ledger_enabled" in context and not isinstance(context["ledger_enabled"], bool):
        raise ValueError("ledger_enabled must be true or false")
    if context.get('science_mode', 'exploration') not in ('exploration', 'validation'):
        raise ValueError('science_mode must be exploration or validation')
    if context.get('science_mode') == 'validation' and context.get('ledger_enabled') is not True:
        raise ValueError('validation mode requires ledger_enabled=true')
    thresholds = context.get("review_thresholds", {})
    if not isinstance(thresholds, dict):
        raise ValueError("review_thresholds must be a JSON object")
    for key, value in thresholds.items():
        if key not in ("quality", "impact", "novelty", "methods", "readiness"):
            raise ValueError(f"unknown review threshold: {key}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 1 <= value <= 10:
            raise ValueError(f"review_thresholds.{key} must be a finite number from 1 to 10")
    for key in ("template_dir", "skills_dir"):
        if key in context and (not isinstance(context[key], str) or not context[key].strip()):
            raise ValueError(f"{key} must be a non-empty directory path string")
    # Avoid command-line/provider options masquerading as complex objects.
    for key in ("code_model", "writer_model", "review_model", "idea_model", "compiler_model", "referee_model"):
        if context.get(key) is not None and not isinstance(context[key], str):
            raise ValueError(f"{key} must be a model name string or null")
    return context
