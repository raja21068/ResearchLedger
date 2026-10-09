from openai import OpenAI
import argparse
import json
import os
from utils import (
    print_log_cost,
    load_accumulated_cost,
    save_accumulated_cost,
    prepare_llm_json_source,
    add_paper_reference_args,
    load_paper_content,
    format_paper_for_prompt,
)


parser = argparse.ArgumentParser()
parser.add_argument('--paper_name', type=str)
parser.add_argument('--gpt_version', type=str)
add_paper_reference_args(parser)
parser.add_argument('--output_dir', type=str, default='')
parser.add_argument(
    '--s1_blueprint_path',
    type=str,
    default='',
    help=(
        'Path to S1 translating_blueprint.txt. If omitted, tries '
        '<output_dir>/translating_blueprint.txt, then ./translating_blueprint.txt.'
    ),
)
parser.add_argument(
    '--reference_output_name',
    type=str,
    default='reference_registry.json',
    help='Filename for the extracted reference registry JSON array.',
)
parser.add_argument(
    '--track_cost',
    action='store_true',
    help=(
        'Optionally update accumulated_cost.json using the existing workflow cost logger. '
        'Disabled by default so the only normal extraction artifact is reference_registry.json.'
    ),
)

args = parser.parse_args()

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

gpt_version = args.gpt_version
paper_format = args.paper_format
output_dir = args.output_dir or '.'
os.makedirs(output_dir, exist_ok=True)

paper_content = load_paper_content(args)
paper_content_str = format_paper_for_prompt(paper_content, paper_format)


def resolve_s1_blueprint_path() -> str:
    candidates = []
    if args.s1_blueprint_path:
        candidates.append(args.s1_blueprint_path)
    candidates.append(os.path.join(output_dir, 'translating_blueprint.txt'))
    candidates.append('translating_blueprint.txt')

    for path in candidates:
        if path and os.path.exists(path):
            return path
    raise FileNotFoundError(
        'Could not find S1 Translating Blueprint. Provide --s1_blueprint_path '
        'or place translating_blueprint.txt in output_dir.'
    )


s1_blueprint_path = resolve_s1_blueprint_path()
with open(s1_blueprint_path, 'r', encoding='utf-8') as f:
    s1_blueprint_str = f.read()

REFERENCE_SYSTEM_PROMPT = """
You are an expert reference extraction agent for paper-to-code reproduction.

This is the REFERENCE EXTRACTING stage, also called S1.5.

Your only task is to extract necessary original paper information for final code generation, following the Large/Verbatim Reference Requests in Section 10.3 of the S1 Translating Blueprint.

S1.5 is NOT a planning stage.
S1.5 is NOT a workflow design stage.
S1.5 is NOT a file architecture stage.
S1.5 is NOT a coding stage.
S1.5 must NOT patch, rewrite, critique, or complete S1.

Allowed extraction scope:
- Extract only raw material requested by S1 Section 10.3.
- Extract only material that exists in the provided paper markdown/text.
- Keep only material useful for final Contracting/Engineering/Coding, such as large tables, long algorithms, prompt templates, output schemas, benchmark formats, dataset schemas, metric/parser references, or long external delegation passages.

Forbidden outputs and behavior:
- Do NOT output metadata.
- Do NOT output s1_backfill_patch.
- Do NOT output unavailable_records.
- Do NOT output quality_checks.
- Do NOT output summaries outside the reference entries.
- Do NOT add new requests that were not in S1 Section 10.3.
- Do NOT extract ordinary short formulas, short facts, or compact algorithm steps unless they are part of a requested long algorithm/table/template.
- Do NOT infer missing implementation details.
- Do NOT use external knowledge beyond the provided paper text and S1.
- Do NOT extract visual internals from figures if they are only image placeholders in markdown.
- Do NOT treat external papers/repos as if their contents were included in this paper.

TEXT-ONLY / FIGURE RULES:
- You can only read the provided markdown/text.
- If a requested figure is represented only by an image placeholder and no relevant caption/surrounding text exists, omit that request from the output.
- If caption or surrounding text contains useful requested content, extract only that text and mark source_availability as caption_only or text_available.
- Do not create placeholder entries for image-only, missing, unavailable, or external-only implementation details.

LARGE TABLE RULES:
- For requested large tables, preserve raw table content if available.
- Also normalize the table into structured rows or modality-specific dictionaries when possible.
- If rowspan/colspan, missing cells, markdown conversion, or OCR artifacts make exact parsing uncertain, set table_parse_risk and explain the ambiguity inside that entry.
- Do not silently repair or complete table values unless the paper text makes the repair obvious.

OUTPUT FORMAT:
Return a single valid JSON array only.
Do not wrap the array in an object.
Do not include markdown outside the JSON.
Do not include commentary outside the JSON.
Use double quotes for all JSON keys and strings.
If no requested reference can be extracted, return [].

Each array item must follow this schema:
{
  "reference_id": "",
  "matched_s1_request_id": "",
  "content_type": "long_prompt_or_output_format | large_table_or_modality_settings | long_algorithm_or_pseudocode | large_metric_or_benchmark_table | dataset_schema_or_file_format | long_external_delegation_passage | other",
  "source_locator": "",
  "source_availability": "text_available | table_available | caption_only | external_delegation_only",
  "extraction_status": "extracted | partially_extracted",
  "extracted_content": "",
  "structured_content": {},
  "normalized_structured_content": {},
  "compact_summary": "",
  "original_information_notes": {
    "what_this_source_contains": "",
    "why_it_matters_for_reproduction": "",
    "which_s1_sections_it_supports": [],
    "likely_downstream_consumers": [],
    "implementation_risks_if_ignored": []
  },
  "limitations": [],
  "table_parse_risk": "",
  "recommended_use": "final_coding_reference | config_table_injection | prompt_template_injection | metric_parser_reference | dataset_loader_reference | documentation_only"
}

IMPORTANT:
- For long algorithms, preserve step order and exact variable names.
- For prompts/templates, preserve exact wording and placeholders.
- For large tables, include raw table content and normalized structured content when possible.
- Keep compact_summary concise.
- Output only the JSON array.
"""

reference_msg = [
    {"role": "system", "content": REFERENCE_SYSTEM_PROMPT},
    {
        "role": "user",
        "content": f"""
Below is the full paper text in {paper_format} format.

[PAPER CONTENT START]
{paper_content_str}
[PAPER CONTENT END]

Below is the S1 Translating Blueprint.

[S1 BLUEPRINT START]
{s1_blueprint_str}
[S1 BLUEPRINT END]

TASK:
Produce the S1.5 reference registry as a single valid JSON array.

Steps:
1. Read Section 10.3 of the S1 blueprint.
2. Extract every Large/Verbatim Reference Request that is actually available in the paper text.
3. For each valid request:
   - if it is long algorithm/pseudocode, preserve step order and exact variable names;
   - if it is a large table, preserve raw table content and also normalize it into structured rows/dictionaries when possible;
   - if it is a prompt/template/output format, preserve exact wording and placeholders;
   - if it is a long external delegation passage, extract only the paper's own delegation text.
4. Omit requests whose source content is missing, image-only, external-only beyond the paper's own statement, or not found.
5. Do not create s1_backfill_patch.
6. Do not output unavailable records, metadata, quality checks, or any other non-registry data.
7. Do not redesign the workflow.
8. Do not add implementation choices.
9. Do not infer missing details.
10. Do not inspect image internals.

Output only a valid JSON array.
"""}
]


def api_call(msg, gpt_version):
    if 'o3-mini' in gpt_version:
        return client.chat.completions.create(
            model=gpt_version,
            reasoning_effort='high',
            messages=msg,
        )
    return client.chat.completions.create(model=gpt_version, messages=msg)


def parse_json_array_response(raw_text: str):
    """Parse the model's JSON array response while tolerating code fences or accidental wrappers."""
    if raw_text is None:
        return []

    prepared = prepare_llm_json_source(raw_text)
    candidates = [prepared, raw_text]

    for text in candidates:
        if not text:
            continue
        try:
            obj = json.loads(text)
            if isinstance(obj, list):
                return obj
            if isinstance(obj, dict) and isinstance(obj.get('reference_registry'), list):
                return obj['reference_registry']
        except Exception:
            pass

    start = raw_text.find('[')
    end = raw_text.rfind(']')
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(raw_text[start:end + 1])
            if isinstance(obj, list):
                return obj
        except Exception:
            pass

    start = raw_text.find('{')
    end = raw_text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(raw_text[start:end + 1])
            if isinstance(obj, dict) and isinstance(obj.get('reference_registry'), list):
                return obj['reference_registry']
        except Exception:
            pass

    return []


def write_json(path: str, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


current_stage = '[Reference Extracting] S1.5 reference registry only'
print(current_stage)

completion = api_call(reference_msg, gpt_version)
completion_json = json.loads(completion.model_dump_json())

if args.track_cost:
    accumulated_cost_path = os.path.join(output_dir, 'accumulated_cost.json')
    total_accumulated_cost = 0
    if os.path.exists(accumulated_cost_path):
        total_accumulated_cost = load_accumulated_cost(accumulated_cost_path)
    total_accumulated_cost = print_log_cost(
        completion_json,
        gpt_version,
        current_stage,
        output_dir,
        total_accumulated_cost,
    )
    save_accumulated_cost(accumulated_cost_path, total_accumulated_cost)

message = completion.choices[0].message
raw_content = message.content or ''
reference_registry = parse_json_array_response(raw_content)

output_path = os.path.join(output_dir, args.reference_output_name)
write_json(output_path, reference_registry)

raw_path = os.path.join(output_dir, 'reference_extraction_raw.txt')
with open(raw_path, 'w', encoding='utf-8') as f:
    f.write(raw_content)

if not reference_registry and raw_content.strip():
    failed_path = os.path.join(output_dir, 'reference_extraction_parse_failed.txt')
    with open(failed_path, 'w', encoding='utf-8') as f:
        f.write(raw_content)
    print(
        f'[Reference Extracting] Warning: parse failed; saved raw output to {failed_path}'
    )
    raise SystemExit(1)

print(f'[Reference Extracting] Saved {len(reference_registry)} reference entries to {output_path}')
