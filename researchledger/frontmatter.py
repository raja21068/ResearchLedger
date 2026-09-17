"""Parsing for the YAML-frontmatter + Markdown-body files evidence, claims and
decisions are stored as (see reference/research-assets.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

_FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


@dataclass
class ParsedDocument:
    frontmatter: dict
    body: str


def parse_document(text: str) -> ParsedDocument:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return ParsedDocument({}, text)
    data = yaml.safe_load(match.group(1)) or {}
    if not isinstance(data, dict):
        data = {}
    return ParsedDocument(data, text[match.end():])


def render_document(frontmatter: dict, body: str) -> str:
    """The inverse of parse_document — used by migrate/evidence-create so new
    writes use real YAML lists/maps instead of comma-joined strings.
    """
    header = yaml.safe_dump(frontmatter, sort_keys=False, default_flow_style=False, allow_unicode=True)
    body_text = body if body.startswith("\n") else "\n" + body
    return f"---\n{header}---\n{body_text}"


def split_ids(value) -> list[str]:
    """Split a comma- or pipe-delimited id list, per the workspace convention.

    Accepts an actual YAML list too, for forward compatibility.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    if not text or text.lower() in ("none", "(none)"):
        return []
    delimiter = "|" if "|" in text else ","
    return [part.strip() for part in text.split(delimiter) if part.strip()]
