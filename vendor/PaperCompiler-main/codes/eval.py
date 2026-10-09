from openai import OpenAI
import json
import os
import re
import sys
import argparse
from utils import (
    extract_json_from_string,
    get_now_str,
    num_tokens_from_messages,
    print_log_cost,
    read_all_files,
    strip_reasoning_suffix,
)

client = OpenAI(api_key = os.environ["OPENAI_API_KEY"])

def api_call(request_json):
    completion = client.chat.completions.create(**request_json)
    return completion

def extract_eval_result_json(content):
    json_block_src = strip_reasoning_suffix(content)

    match = re.search(r"```json\n(.*?)\n```", json_block_src, re.DOTALL)
    if not match:
        match = re.search(r"```json\\n(.*?)\\n```", json_block_src, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        start_idx = json_block_src.find("{")
        end_idx = json_block_src.rfind("}")
        if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
            return None, ""
        json_str = json_block_src[start_idx : end_idx + 1]

    try:
        return json.loads(json_str), json_str
    except json.JSONDecodeError:
        recovered = extract_json_from_string(json_block_src)
        if recovered:
            try:
                return json.loads(recovered), recovered
            except json.JSONDecodeError:
                pass
        return None, json_str


def save_eval_text_outputs(eval_result_dir, base_name, raw_outputs):
    txt_path = f"{eval_result_dir}/{base_name}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        for idx, content in enumerate(raw_outputs, 1):
            f.write(f"===== SAMPLE {idx} =====\n")
            f.write(content)
            f.write("\n\n")
    return txt_path


def save_parsed_eval_outputs(eval_result_dir, base_name, parsed_outputs, failed_raw_outputs):
    parsed_path = f"{eval_result_dir}/{base_name}_parsed.json"
    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(parsed_outputs, f, ensure_ascii=False, indent=2)

    raw_path = ""
    if failed_raw_outputs:
        raw_path = f"{eval_result_dir}/{base_name}_parsed_raw.txt"
        with open(raw_path, "w", encoding="utf-8") as f:
            for idx, content in enumerate(failed_raw_outputs, 1):
                f.write(f"===== SAMPLE {idx} =====\n")
                f.write(content)
                f.write("\n\n")
    return parsed_path, raw_path


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
            print("[ERROR] --pdf_markdown_path is required when --paper_format is Markdown.")
            sys.exit(1)
        with open(args.pdf_markdown_path, encoding="utf-8") as f:
            return f.read()
    print("[ERROR] Invalid paper format. Please select 'JSON', 'LaTeX', or 'Markdown'.")
    sys.exit(1)


def main(args):

    paper_name = args.paper_name
    output_dir = args.output_dir  
    target_repo_dir = args.target_repo_dir
    eval_result_dir = args.eval_result_dir
    gpt_version = args.gpt_version
    generated_n = args.generated_n
    data_dir = args.data_dir
    eval_type = args.eval_type
    gold_repo_dir = args.gold_repo_dir

    paper_content = load_paper_content(args)

    target_files_dict = read_all_files(
        target_repo_dir,
        allowed_ext=[".py", ".yaml", ".yml", ".md", ".sh", ".bash", ".txt"],
        is_print=False,
    )
    codes = ""
    for file_name, code in target_files_dict.items():
        codes += f"```text\n## File name: {file_name}\n{code}\n```\n\n"


    prompt = open(f"{data_dir}/prompts/{eval_type}.txt").read()
    
    cur_prompt = (
        prompt.replace('{{Paper}}', f"{paper_content}")
        .replace('{{Code}}', codes)
        .replace('{{File_Count}}', str(len(target_files_dict)))
        .replace('{{File_Structure}}', "\n".join(sorted(target_files_dict)))
    )
    
    # refernce-based
    if "ref_based" == eval_type and len(gold_repo_dir) > 0:
        all_files_dict = read_all_files(gold_repo_dir, allowed_ext=[".py", ".yaml", ".yml", ".md", ".sh", ".bash"], is_print=False)

        goldcodes = ""
        gold_cnt = 0
        if len(args.selected_file_path) > 0:
            selected_file_lst = []
            with open(args.selected_file_path) as f:
                selected_file_lst = f.readlines()
            
            for s_idx in range(len(selected_file_lst)):
                selected_file_lst[s_idx] = selected_file_lst[s_idx].strip() 

            
            for all_file, all_file_code in all_files_dict.items():
                if all_file not in selected_file_lst:
                    continue

                goldcodes += f"```## File name: {all_file}\n{all_file_code}\n```\n\n" 

                gold_cnt += 1


        else:
            for all_file, all_file_code in all_files_dict.items():
                goldcodes += f"```## File name: {all_file}\n{all_file_code}\n```\n\n" 

                gold_cnt += 1

        cur_prompt = cur_prompt.replace('{{GoldCode}}', f"{goldcodes}")

    msg = [{"role": "system", "content": cur_prompt}]

    try:
        num_tokens = num_tokens_from_messages(msg)
    except Exception as e:
        print(f"[WARNING] An exception was raised while counting tokens for the target repository of {args.paper_name}.")
        print(e)
        print("-"*40)
        num_tokens = 0
    

    # Removed token limit check to allow larger contexts
    

    if "o3-mini" in gpt_version:
        if generated_n > 8:
            print(f"[WARNING] o3-mini does not support n > 8. Setting generated_n to 8.")
            generated_n = 8

        request_json = {
                "model": gpt_version, 
                "messages": msg,
                "reasoning_effort": "high",
                "n": generated_n
        }
    else:
        request_json = {
                "model": gpt_version, 
                "messages": msg, 
                "temperature": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "stop": None,
                "n": generated_n # 10
        }
        
    completion = api_call(request_json)
    completion_json = json.loads(completion.model_dump_json())
        
    score_key = "score"
    rationale_key = "critique_list"


    all_scores = []
    rationales = []
    raw_outputs = []
    parsed_outputs = []
    failed_raw_outputs = []
    for n in range(generated_n):    
        choice = completion_json['choices'][n]

        output = strip_reasoning_suffix(choice['message']['content'])
        raw_outputs.append(output)
        
        try:
            output_json2 = json.loads(output)
            score = int(output_json2[score_key])

            if isinstance(output_json2[rationale_key], str):
                rationale = output_json2[rationale_key]
            else:
                rationale = json.dumps(output_json2[rationale_key])
        except Exception as e:
            # print(e)             
            try:
                output_json2, _ = extract_eval_result_json(output)
                if output_json2 is None:
                    raise ValueError("Failed to parse evaluation JSON from model output.")
                score = int(output_json2[score_key])

                if isinstance(output_json2[rationale_key], str):
                    rationale = output_json2[rationale_key]
                else:
                    rationale = json.dumps(output_json2[rationale_key])
            except Exception as e2: # Parsing Error
                print(f"[WARNING] Invalid repsponse: parsing error")
                print(e2)
                print("-"*40)
                failed_raw_outputs.append(output)
                continue

        parsed_outputs.append(output_json2)
            
        # score
        if score < 1 or score > 5:
            print(f"[WARNING] Invalid repsponse: score {score}, Score must be in the range of 1–5.")
            continue
        
        all_scores.append(int(score))
        rationales.append(rationale)
        

    if all_scores:
        avg_score = sum(all_scores) / len(all_scores)
    else:
        avg_score = 0.0

    now_str = get_now_str()
    base_name = f"{paper_name}_eval_{eval_type}_{gpt_version}_{now_str}"
    os.makedirs(eval_result_dir, exist_ok=True)
    save_eval_text_outputs(eval_result_dir, base_name, raw_outputs)
    parsed_path, parsed_raw_path = save_parsed_eval_outputs(
        eval_result_dir, base_name, parsed_outputs, failed_raw_outputs
    )

    output_json= {
        "paper_name": paper_name,
        "eval_type": eval_type,
        "gpt_version": gpt_version,
        "target_repo_dir": target_repo_dir,
        "gold_repo_dir": gold_repo_dir,
        "generated_n": generated_n,
        "request_json": request_json,
        "completion_json": completion_json,
        "eval_result": {
            "score": avg_score,
            "valid_n": len(all_scores),
            "scroe_lst": all_scores,
            "rationale_lst": rationales,    
        },
        "artifact_paths": {
            "response_txt": f"{eval_result_dir}/{base_name}.txt",
            "parsed_json": parsed_path,
            "parsed_raw_txt": parsed_raw_path,
        },
    }
    
    with open(f"{eval_result_dir}/{base_name}.json", 'w', encoding='utf-8') as f:
        json.dump(output_json, f)

    
    # ---------------
    print()
    print("=" * 40)
    print("🌟 Evaluation Summary 🌟")
    print(f"📄 Paper name: {paper_name}")
    print(f"🧪 Evaluation type: {eval_type}")
    print(f"📁 Target repo directory: {target_repo_dir}")
    print(f"📊 Evaluation result:")
    print(f"\t📈 Score: {avg_score:.4f}")
    print(f"\t✅ Valid: {output_json['eval_result']['valid_n']}/{generated_n}")
    print("=" * 40)
    
    print_log_cost(completion_json, gpt_version, f"[Evaluation] {paper_name} - {eval_type}", output_dir, 0)
    # ---------------


if __name__ == '__main__':

    argparser = argparse.ArgumentParser()
    
    argparser.add_argument('--paper_name', type=str)
    argparser.add_argument('--paper_format', type=str, default="JSON", choices=["JSON", "LaTeX", "Markdown"])
    argparser.add_argument('--pdf_json_path', type=str, default="")
    argparser.add_argument('--pdf_latex_path', type=str, default="")
    argparser.add_argument('--pdf_markdown_path', type=str, default="")
    argparser.add_argument('--data_dir',type=str, default="../data")

    argparser.add_argument('--output_dir',type=str)
    
    argparser.add_argument('--target_repo_dir', type=str)
    argparser.add_argument('--gold_repo_dir', type=str, default="")
    argparser.add_argument('--eval_result_dir',type=str)
    
    argparser.add_argument('--eval_type', type=str, default="ref_free", choices=["ref_free", "ref_free_ex", "ref_based"])

    argparser.add_argument('--generated_n', type=int, default=8)
    argparser.add_argument('--gpt_version', type=str, default="o3-mini")

    argparser.add_argument('--selected_file_path', type=str, default="") 
    args = argparser.parse_args()
    main(args)
