# Reference Prompts: Submission Formatting and Compile Repair

## Source Prompts (verbatim from ConvFusion)

These are the original module prompts this skill was reorganised from — preserved as
accumulated research intelligence, not as an execution contract. They reference state keys
(`{research_topic}`, `{plans_json}`, …) that no longer exist in v2; read them for the method,
not for a pipeline.

### `modules/paper/latex/prompts/latex_validator_prompt.py` — TEMPLATE

```text
You are a LaTeX expert. Fix ALL compilation errors in the provided LaTeX document.

## LaTeX Document:
```latex
{latex_document}
```

## Compile Logs (read carefully — each error must be addressed):
```
{compile_log}
```

## Critical Error Patterns to Fix:
1. "macro parameter character #" / "# in vertical mode" → Remove or escape ALL raw # characters.
   - If the text contains Markdown headings (###, ####), remove the # marks and keep only the heading text.
   - Never use # for emphasis or formatting in LaTeX.
2. "Undefined control sequence" / "Missing \\begin{{document}}" → Add missing \\usepackage or fix typos.
3. "Unclosed environment" → Match every \\begin{{X}} with a corresponding \\end{{X}}.
4. "Missing $" / "Invalid math mode" → Properly wrap math expressions in $...$ or $$...$$.
5. Underfull/Overfull hbox → These are warnings, only fix if they cause visible layout issues.
6. Unescaped special characters: % → \\%, & → \\&, _ → \\_, $ → \\$, {{ → \\{{, }} → \\}}.
7. **Bold Markdown** (`**text**`) → Replace with `\\textbf{{text}}`.
8. *Italic Markdown* (`*text*`) → Replace with `\\textit{{text}}`.
9. Blank or empty environments → Remove if they contain no content.

## Rules (STRICT):
1. Fix ONLY the lines with compilation errors shown above
2. Maintain the original indentation and structure
3. Output ONLY the fixed lines — exactly the same number of lines as the input context
4. Do NOT include ```latex``` fences
5. Do NOT add explanations or comments
6. Ensure the fixed code is syntactically valid LaTeX
7. If a line doesn't need fixing, keep it exactly as is
8. Focus on the most common LaTeX compilation issues:
   - Missing or mismatched braces/brackets
   - Undefined control sequences
   - Missing character handling or replacements
   - Environment mismatches

Output ONLY a valid JSON object with exactly this field:
{{
  "latex_document": "<the fixed LaTeX code, same number of lines as input>"
}}

CRITICAL: Output ONLY the JSON object — no markdown fences, no explanations.
```

### `modules/paper/narrative/prompts/reference_prompt.py` — IEEE_TEMPLATE

```text
You are formatting the References section for an IEEE Transactions paper.

Generate a comprehensive, properly formatted reference list in IEEE journal style.

Cited Papers (to be included in references):
{cited_papers_info}

All Papers (from Discovery module, for complete reference data):
{all_papers_info}

Requirements:
1. Format all references in IEEE journal style: [N] A. Author, B. Author, and C. Author, "Title of the paper," IEEE Trans. Pattern Anal. Mach. Intell., vol. xx, no. xx, pp. xx-xx, Month Year.
2. Order references sequentially by number [1], [2], ...
3. If authors are available, use format: [N] A. Author, B. Author, and C. Author, "Title of the paper," IEEE Trans. ..., vol. xx, no. xx, pp. xx-xx, Month Year.
4. If authors are NOT available, SKIP the author part entirely and start directly with the title: [N] "Title of the paper," IEEE Trans. ..., vol. xx, no. xx, pp. xx-xx, Month Year.
5. DO NOT use "Anonymous" as author name under any circumstances. Either use real author names or omit the author part.
6. Use all available metadata (authors, title, venue, year, volume, issue, pages) to construct complete citations
7. If year is missing or 0, omit it
8. If venue is missing, omit the venue part
9. If pages are missing, omit pp. xx-xx
10. DO NOT include placeholder text like "A. Author", "B. Author", "Title", "IEEE Trans...", "Month Year", "pp. xx-xx"
11. DO NOT repeat citations with the same number
12. Ensure consistency in formatting across all references

Important:
- Do NOT generate placeholder references
- Use actual paper data from the provided papers
- For each cited paper, generate the most complete IEEE citation possible with whatever metadata is available

Output JSON format (CRITICAL: ONLY output JSON, NO additional text, NO markdown, NO explanations): {{"references": "[1] A. Author, B. Author, and C. Author, \"Title,\" IEEE Trans. ..., vol. x, no. x, pp. xx-xx, 2024.\\n[2] ..."}}
```

## Error Information:
{error_message}

## LaTeX Code Context (error line marked with →):
```latex
{error_context}
```

## Rules (STRICT):
1. Fix ONLY the lines with compilation errors shown above
2. Maintain the original indentation and structure
3. Output ONLY the fixed lines — exactly the same number of lines as the input context
4. Do NOT include ```latex``` fences
5. Do NOT add explanations or comments
6. Ensure the fixed code is syntactically valid LaTeX
7. If a line doesn't need fixing, keep it exactly as is
8. Focus on the most common LaTeX compilation issues:
   - Missing or mismatched braces/brackets
   - Undefined control sequences
   - Missing character handling or replacements
   - Environment mismatches

Output ONLY a valid JSON object with exactly this field:
{{
  "latex_document": "<the fixed LaTeX code, same number of lines as input>"
}}

CRITICAL: Output ONLY the JSON object — no markdown fences, no explanations.
```

### `modules/paper/narrative/prompts/reference_prompt.py` — IEEE_TEMPLATE

```text
You are formatting the References section for an IEEE Transactions paper.

Generate a comprehensive, properly formatted reference list in IEEE journal style.

Cited Papers (to be included in references):
{cited_papers_info}

All Papers (from Discovery module, for complete reference data):
{all_papers_info}

Requirements:
1. Format all references in IEEE journal style: [N] A. Author, B. Author, and C. Author, "Title of the paper," IEEE Trans. Pattern Anal. Mach. Intell., vol. xx, no. xx, pp. xx-xx, Month Year.
2. Order references sequentially by number [1], [2], ...
3. If authors are available, use format: [N] A. Author, B. Author, and C. Author, "Title of the paper," IEEE Trans. ..., vol. xx, no. xx, pp. xx-xx, Month Year.
4. If authors are NOT available, SKIP the author part entirely and start directly with the title: [N] "Title of the paper," IEEE Trans. ..., vol. xx, no. xx, pp. xx-xx, Month Year.
5. DO NOT use "Anonymous" as author name under any circumstances. Either use real author names or omit the author part.
6. Use all available metadata (authors, title, venue, year, volume, issue, pages) to construct complete citations
7. If year is missing or 0, omit it
8. If venue is missing, omit the venue part
9. If pages are missing, omit pp. xx-xx
10. DO NOT include placeholder text like "A. Author", "B. Author", "Title", "IEEE Trans...", "Month Year", "pp. xx-xx"
11. DO NOT repeat citations with the same number
12. Ensure consistency in formatting across all references

Important:
- Do NOT generate placeholder references
- Use actual paper data from the provided papers
- For each cited paper, generate the most complete IEEE citation possible with whatever metadata is available

Output JSON format (CRITICAL: ONLY output JSON, NO additional text, NO markdown, NO explanations): {{"references": "[1] A. Author, B. Author, and C. Author, \"Title,\" IEEE Trans. ..., vol. x, no. x, pp. xx-xx, 2024.\\n[2] ..."}}
```
