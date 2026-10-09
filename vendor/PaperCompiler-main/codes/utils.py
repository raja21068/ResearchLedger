import json
import re
import os
import sys
from datetime import datetime

PAPER_REFERENCE_INSTRUCTION = (
    "REFERENCE PAPER (authoritative): The full paper text is included below. "
    "When blueprint, DAG, routing, stubs, or hyperparameter summaries conflict with the paper, "
    "follow the paper. Ground decisions in explicit equations, tables, and implementation details."
)


def add_paper_reference_args(parser):
    parser.add_argument(
        "--paper_format",
        type=str,
        default="Markdown",
        choices=["JSON", "LaTeX", "Markdown"],
    )
    parser.add_argument("--pdf_json_path", type=str, default="")
    parser.add_argument("--pdf_latex_path", type=str, default="")
    parser.add_argument("--pdf_markdown_path", type=str, default="")
    return parser


def load_paper_content(args):
    paper_format = args.paper_format
    if paper_format == "JSON":
        if not args.pdf_json_path:
            print("[ERROR] --pdf_json_path is required when --paper_format is JSON.")
            sys.exit(1)
        with open(args.pdf_json_path, encoding="utf-8") as f:
            return json.load(f)
    if paper_format == "LaTeX":
        if not args.pdf_latex_path:
            print("[ERROR] --pdf_latex_path is required when --paper_format is LaTeX.")
            sys.exit(1)
        with open(args.pdf_latex_path, encoding="utf-8") as f:
            return f.read()
    if paper_format == "Markdown":
        if not args.pdf_markdown_path:
            print(
                "[ERROR] --pdf_markdown_path is required when --paper_format is Markdown."
            )
            sys.exit(1)
        with open(args.pdf_markdown_path, encoding="utf-8") as f:
            return f.read()
    print("[ERROR] Invalid paper format. Please select 'JSON', 'LaTeX', or 'Markdown'.")
    sys.exit(1)


def format_paper_for_prompt(paper_content, paper_format):
    if paper_format == "JSON":
        if isinstance(paper_content, str):
            return paper_content
        return json.dumps(paper_content, ensure_ascii=False, indent=2)
    return paper_content if isinstance(paper_content, str) else str(paper_content)


def build_paper_reference_block(paper_content_str):
    return f"""{PAPER_REFERENCE_INSTRUCTION}

[PAPER CONTENT START]
{paper_content_str}
[PAPER CONTENT END]"""

def extract_planning(trajectories_json_file_path):
    with open(trajectories_json_file_path) as f:
        traj = json.load(f)

    context_lst = []
    for turn in traj:
        if turn['role'] == 'assistant':
            # context_lst.append(turn['content'])
            content = turn['content']
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            context_lst.append(content)


    context_lst = context_lst[:3] 

    return context_lst


_SCRATCHPAD_CLOSE_RE = re.compile(r"</([a-zA-Z0-9_]+_scratchpad)>", re.IGNORECASE)


def strip_reasoning_suffix(content):
    if "</think>" in content:
        return content.split("</think>")[-1].strip()
    return content.strip()


def strip_scratchpad_suffix(content):
    matches = list(_SCRATCHPAD_CLOSE_RE.finditer(content))
    if matches:
        return content[matches[-1].end() :].strip()
    return content.strip()


def prepare_llm_json_source(content):
    return strip_scratchpad_suffix(strip_reasoning_suffix(content))


def _strip_json_comments(text):
    """Remove // and /* */ comments outside of quoted strings."""
    out = []
    i = 0
    n = len(text)
    in_string = False
    escape = False
    quote = ""
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = True
            quote = ch
            out.append(ch)
            i += 1
            continue

        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2 if i + 1 < n else 1
            continue

        if ch == "/" and nxt == "/":
            i += 2
            while i < n and text[i] not in ("\n", "\r"):
                i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def _parse_json_candidate(json_str):
    try:
        return json.loads(json_str), json_str
    except json.JSONDecodeError:
        pass

    sanitized = _strip_json_comments(json_str)
    if sanitized != json_str:
        try:
            return json.loads(sanitized), sanitized
        except json.JSONDecodeError:
            pass

    return None, json_str


def _extract_balanced_json_object(text, start_idx=0):
    start_idx = text.find("{", start_idx)
    if start_idx == -1:
        return None, ""

    depth = 0
    in_string = False
    escape = False
    quote = ""

    for i in range(start_idx, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
            continue
        if ch in ('"', "'"):
            in_string = True
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return _parse_json_candidate(text[start_idx : i + 1])

    return None, text[start_idx:]


def _extract_json_with_required_keys(text, required_keys):
    start = 0
    while True:
        idx = text.find("{", start)
        if idx == -1:
            break
        obj, raw = _extract_balanced_json_object(text, idx)
        if not raw:
            break
        if obj is not None and all(key in obj for key in required_keys):
            return obj, raw
        start = idx + 1
    return None, ""


def _extract_json_from_section(section):
    fenced = re.search(r"```json\n(.*?)\n```", section, re.DOTALL)
    if not fenced:
        fenced = re.search(r"```json\\n(.*?)\\n```", section, re.DOTALL)
    if fenced:
        return _parse_json_candidate(fenced.group(1))

    return _extract_balanced_json_object(section)


def _json_result_matches_keys(result, required_keys):
    if result[0] is None:
        return False
    if not required_keys:
        return True
    return all(key in result[0] for key in required_keys)


def extract_json_from_llm_response(content, required_keys=None):
    """Parse JSON after </*_scratchpad>; optional required_keys filter false positives."""
    src = prepare_llm_json_source(content)

    marker = re.search(
        r"STEP\s*2\s*:\s*THE\s+(?:ALIGNMENT|ROUTING|JSON)\s+(?:JSON|BLUEPRINT)?",
        src,
        re.IGNORECASE,
    )
    if marker:
        result = _extract_json_from_section(src[marker.end() :].strip())
        if _json_result_matches_keys(result, required_keys):
            return result

    result = _extract_json_from_section(src)
    if _json_result_matches_keys(result, required_keys):
        return result

    if required_keys:
        return _extract_json_with_required_keys(src, required_keys)

    return _extract_balanced_json_object(src)


def extract_blueprint_json(content):
    return extract_json_from_llm_response(
        content, ["metadata", "model_architecture"]
    )


def extract_reconciling_json(content):
    """Parse Stage-2 reconciling spec (new schema first, legacy aligning DAG fallback)."""
    result = extract_json_from_llm_response(
        content, ["method_graph", "core_path_contracts"]
    )
    if result[0] is not None:
        return result
    return extract_json_from_llm_response(
        content, ["global_tensors", "computation_graph"]
    )


def extract_routing_json(content):
    return extract_json_from_llm_response(content, ["file_tree"])


def extract_code_from_content(content):
    content = prepare_llm_json_source(content)
    pattern = r'^```(?:\w+)?\s*\n(.*?)(?=^```)```'
    code = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
    if len(code) == 0:
        return ""
    else:
        return code[0]
    
def cal_cost(response_json, model_name):
    model_cost = {
        # gpt-4.1
        "gpt-4.1": {"input": 2.00, "cached_input": 0.50, "output": 8.00},
        "gpt-4.1-2025-04-14": {"input": 2.00, "cached_input": 0.50, "output": 8.00},

        # gpt-4.1-mini
        "gpt-4.1-mini": {"input": 0.40, "cached_input": 0.10, "output": 1.60},
        "gpt-4.1-mini-2025-04-14": {"input": 0.40, "cached_input": 0.10, "output": 1.60},

        # gpt-4.1-nano
        "gpt-4.1-nano": {"input": 0.10, "cached_input": 0.025, "output": 0.40},
        "gpt-4.1-nano-2025-04-14": {"input": 0.10, "cached_input": 0.025, "output": 0.40},

        # gpt-4.5-preview
        "gpt-4.5-preview": {"input": 75.00, "cached_input": 37.50, "output": 150.00},
        "gpt-4.5-preview-2025-02-27": {"input": 75.00, "cached_input": 37.50, "output": 150.00},

        # gpt-4o
        "gpt-4o": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
        "gpt-4o-2024-08-06": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
        "gpt-4o-2024-11-20": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
        "gpt-4o-2024-05-13": {"input": 5.00, "cached_input": None, "output": 15.00},

        # gpt-4o-audio-preview
        "gpt-4o-audio-preview": {"input": 2.50, "cached_input": None, "output": 10.00},
        "gpt-4o-audio-preview-2024-12-17": {"input": 2.50, "cached_input": None, "output": 10.00},
        "gpt-4o-audio-preview-2024-10-01": {"input": 2.50, "cached_input": None, "output": 10.00},

        # gpt-4o-realtime-preview
        "gpt-4o-realtime-preview": {"input": 5.00, "cached_input": 2.50, "output": 20.00},
        "gpt-4o-realtime-preview-2024-12-17": {"input": 5.00, "cached_input": 2.50, "output": 20.00},
        "gpt-4o-realtime-preview-2024-10-01": {"input": 5.00, "cached_input": 2.50, "output": 20.00},

        # gpt-4o-mini
        "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
        "gpt-4o-mini-2024-07-18": {"input": 0.15, "cached_input": 0.075, "output": 0.60},

        # gpt-4o-mini-audio-preview
        "gpt-4o-mini-audio-preview": {"input": 0.15, "cached_input": None, "output": 0.60},
        "gpt-4o-mini-audio-preview-2024-12-17": {"input": 0.15, "cached_input": None, "output": 0.60},

        # gpt-4o-mini-realtime-preview
        "gpt-4o-mini-realtime-preview": {"input": 0.60, "cached_input": 0.30, "output": 2.40},
        "gpt-4o-mini-realtime-preview-2024-12-17": {"input": 0.60, "cached_input": 0.30, "output": 2.40},

        # o1
        "o1": {"input": 15.00, "cached_input": 7.50, "output": 60.00},
        "o1-2024-12-17": {"input": 15.00, "cached_input": 7.50, "output": 60.00},
        "o1-preview-2024-09-12": {"input": 15.00, "cached_input": 7.50, "output": 60.00},

        # o1-pro
        "o1-pro": {"input": 150.00, "cached_input": None, "output": 600.00},
        "o1-pro-2025-03-19": {"input": 150.00, "cached_input": None, "output": 600.00},

        # o3
        "o3": {"input": 10.00, "cached_input": 2.50, "output": 40.00},
        "o3-2025-04-16": {"input": 10.00, "cached_input": 2.50, "output": 40.00},

        # o4-mini
        "o4-mini": {"input": 1.10, "cached_input": 0.275, "output": 4.40},
        "o4-mini-2025-04-16": {"input": 1.10, "cached_input": 0.275, "output": 4.40},

        # o3-mini
        "o3-mini": {"input": 1.10, "cached_input": 0.55, "output": 4.40},
        "o3-mini-2025-01-31": {"input": 1.10, "cached_input": 0.55, "output": 4.40},

        # gpt-5-mini
        "gpt-5-mini": {"input": 1.10, "cached_input": 0.55, "output": 4.40},
        "gpt-5-mini-2025-12-01": {"input": 1.10, "cached_input": 0.55, "output": 4.40},

        # o1-mini
        "o1-mini": {"input": 1.10, "cached_input": 0.55, "output": 4.40},
        "o1-mini-2024-09-12": {"input": 1.10, "cached_input": 0.55, "output": 4.40},

        # gpt-4o-mini-search-preview
        "gpt-4o-mini-search-preview": {"input": 0.15, "cached_input": None, "output": 0.60},
        "gpt-4o-mini-search-preview-2025-03-11": {"input": 0.15, "cached_input": None, "output": 0.60},

        # gpt-4o-search-preview
        "gpt-4o-search-preview": {"input": 2.50, "cached_input": None, "output": 10.00},
        "gpt-4o-search-preview-2025-03-11": {"input": 2.50, "cached_input": None, "output": 10.00},

        # computer-use-preview
        "computer-use-preview": {"input": 3.00, "cached_input": None, "output": 12.00},
        "computer-use-preview-2025-03-11": {"input": 3.00, "cached_input": None, "output": 12.00},

        # gpt-image-1
        "gpt-image-1": {"input": 5.00, "cached_input": None, "output": None},
    }

    
    prompt_tokens = response_json["usage"]["prompt_tokens"]
    completion_tokens = response_json["usage"]["completion_tokens"]
    cached_tokens = response_json["usage"]["prompt_tokens_details"].get("cached_tokens", 0)

    # input token = (prompt_tokens - cached_tokens)
    actual_input_tokens = prompt_tokens - cached_tokens
    output_tokens = completion_tokens

    try:
        cost_info = model_cost[model_name]
    except KeyError:
        fallback = model_cost.get('o3-mini') or next(iter(model_cost.values()))
        print(f"[WARNING] Unknown model '{model_name}' for cost calculation. Falling back to o3-mini cost rates.")
        cost_info = fallback

    input_cost = (actual_input_tokens / 1_000_000) * cost_info['input']
    cached_input_cost = (cached_tokens / 1_000_000) * cost_info['cached_input']
    output_cost = (output_tokens / 1_000_000) * cost_info['output']

    total_cost = input_cost + cached_input_cost + output_cost

    return {
        'model_name': model_name,
        'actual_input_tokens': actual_input_tokens,
        'input_cost': input_cost,
        'cached_tokens': cached_tokens,
        'cached_input_cost': cached_input_cost,
        'output_tokens': output_tokens,
        'output_cost': output_cost,
        'total_cost': total_cost,
    }

def load_accumulated_cost(accumulated_cost_file):
    if os.path.exists(accumulated_cost_file):
        with open(accumulated_cost_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("total_cost", 0.0)
    else:
        return 0.0

def save_accumulated_cost(accumulated_cost_file, cost):
    with open(accumulated_cost_file, "w", encoding="utf-8") as f:
        json.dump({"total_cost": cost}, f)

def print_response(completion_json, is_llm=False):
    print("============================================")
    if is_llm:
        print(completion_json['text'])
    else:
        print(completion_json['choices'][0]['message']['content'])
    print("============================================\n")

def print_log_cost(completion_json, gpt_version, current_stage, output_dir, total_accumulated_cost):
    usage_info = cal_cost(completion_json, gpt_version)

    current_cost = usage_info['total_cost']
    total_accumulated_cost += current_cost

    output_lines = []
    output_lines.append("🌟 Usage Summary 🌟")
    output_lines.append(f"{current_stage}")
    output_lines.append(f"🛠️ Model: {usage_info['model_name']}")
    output_lines.append(f"📥 Input tokens: {usage_info['actual_input_tokens']} (Cost: ${usage_info['input_cost']:.8f})")
    output_lines.append(f"📦 Cached input tokens: {usage_info['cached_tokens']} (Cost: ${usage_info['cached_input_cost']:.8f})")
    output_lines.append(f"📤 Output tokens: {usage_info['output_tokens']} (Cost: ${usage_info['output_cost']:.8f})")
    output_lines.append(f"💵 Current total cost: ${current_cost:.8f}")
    output_lines.append(f"🪙 Accumulated total cost so far: ${total_accumulated_cost:.8f}")
    output_lines.append("============================================\n")

    output_text = "\n".join(output_lines)
    
    print(output_text)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(f"{output_dir}/cost_info.log", "a", encoding="utf-8") as f:
        f.write(output_text + "\n")
    
    return total_accumulated_cost


def num_tokens_from_messages(messages, model="gpt-4o-2024-08-06"):
    import tiktoken
    
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using o200k_base encoding.")
        encoding = tiktoken.get_encoding("o200k_base")
    if model in {
        "gpt-3.5-turbo-0125",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        "gpt-4o-mini-2024-07-18",
        "gpt-4o-2024-08-06"
        }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif "gpt-3.5-turbo" in model:
        print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0125.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0125")
    elif "gpt-4o-mini" in model:
        print("Warning: gpt-4o-mini may update over time. Returning num tokens assuming gpt-4o-mini-2024-07-18.")
        return num_tokens_from_messages(messages, model="gpt-4o-mini-2024-07-18")
    elif "gpt-4o" in model:
        print("Warning: gpt-4o and gpt-4o-mini may update over time. Returning num tokens assuming gpt-4o-2024-08-06.")
        return num_tokens_from_messages(messages, model="gpt-4o-2024-08-06")

    elif "gpt-4" in model:
        print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            # num_tokens += len(encoding.encode(value) 
            num_tokens += len(encoding.encode(value, allowed_special={"<|endoftext|>"},disallowed_special=()))
            
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens



def read_all_files(directory, allowed_ext, is_print=True): 
    """Recursively read all .py files in the specified directory and return their contents."""
    all_files_content = {}
    
    for root, _, files in os.walk(directory):  # Recursively traverse directories
        for filename in files:
            relative_path = os.path.relpath(os.path.join(root, filename), directory)  # Preserve directory structure

            # print(f"fn: {filename}\tdirectory: {directory}")
            _file_name, ext = os.path.splitext(filename)
            
            is_skip = False
            if len(directory) < len(root):
                root2 = root[len(directory)+1:]
                for dirname in root2.split("/"):
                    if dirname.startswith("."):
                        is_skip = True
                        break
            
            if filename.startswith(".") or "requirements.txt" in filename or ext == "" or is_skip:
                if is_print and ext == "":
                    print(f"[SKIP] {os.path.join(root, filename)}")
                continue
                
            if ext not in allowed_ext:
                if _file_name.lower() != "readme": 
                    if is_print:
                        print(f"[SKIP] {os.path.join(root, filename)}")
                    continue

            try:
                filepath = os.path.join(root, filename)
                file_size = os.path.getsize(filepath) # bytes
                
                if file_size > 204800: # > 200KB 
                    print(f"[BIG] {filepath} {file_size}")

                with open(filepath, "r") as file: # encoding="utf-8"
                    all_files_content[relative_path] = file.read()
            except Exception as e:
                print(e)
                print(f"[SKIP] {os.path.join(root, filename)}")
    
    
    return all_files_content

def extract_json_from_string(text):
    # Extract content inside ```yaml\n...\n```
    match = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)

    if match:
        yaml_content = match.group(1)
        return yaml_content
    else:
        print("No JSON content found.")
        return ""


def get_now_str():
    now = datetime.now()
    now = str(now)
    now = now.split(".")[0]
    now = now.replace("-","").replace(" ","_").replace(":","")
    return now # now - "20250427_205124"
