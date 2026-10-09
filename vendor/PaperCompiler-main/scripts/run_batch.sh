#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GOLD_REPO_BASE="${GOLD_REPO_BASE:-${ROOT}/gold_repos}"
RUN_SCRIPT="${SCRIPT_DIR}/run.sh"

GPT_VERSION="${GPT_VERSION:-o3-mini}"
EVAL_MODEL="${EVAL_MODEL:-o3-mini}"
GENERATED_N="${GENERATED_N:-8}"
FORCE_RERUN="${FORCE_RERUN:-0}"

PIPELINE="papercompiler_o3mini"
CONFERENCES="${CONFERENCES:-iclr2024 icml2024 nips2024}"
DATA_ROOT="${DATA_ROOT:-${ROOT}/data/paper2code}"
OUTPUTS_ROOT="${OUTPUTS_ROOT:-${ROOT}/outputs}"

CURRENT_CONFERENCE=""
PAPER_DIR=""
CURRENT_PAPER_FORMAT=""
BATCH_ROOT=""
RUN_INDEX=""
RUN_LOG=""
STATS_CSV=""
STATS_JSON=""
SUMMARY_TXT=""

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="python3"
    else
        PYTHON_BIN="python"
    fi
fi

log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $*" | tee -a "${RUN_LOG}"
}

paper_name_from_input() {
    local input_path="$1"
    local file_name
    file_name="$(basename "${input_path}")"
    if [[ "${file_name}" == *_cleaned.json ]]; then
        echo "${file_name%_cleaned.json}"
    else
        echo "${file_name%.pdf}"
    fi
}

has_repo_code() {
    local repo_dir="$1"
    [[ -d "${repo_dir}" ]] && [[ -n "$(find "${repo_dir}" -type f -name '*.py' -print -quit 2>/dev/null)" ]]
}

has_eval_artifact() {
    local eval_dir="$1"
    local paper_name="$2"
    local eval_type="$3"
    local pattern="${eval_dir}/${paper_name}_eval_${eval_type}_${EVAL_MODEL}_"*.json
    local match
    for match in ${pattern}; do
        if [[ -f "${match}" ]] && [[ "${match}" != *"_parsed.json" ]]; then
            return 0
        fi
    done
    return 1
}

is_run_complete() {
    local paper_name="$1"
    local output_dir="$2"
    local repo_dir="$3"
    has_repo_code "${repo_dir}" || return 1
    [[ -f "${output_dir}/translating_blueprint.txt" ]] || return 1
    [[ -f "${output_dir}/reference_registry.json" ]] || return 1
    [[ -f "${output_dir}/reconciling_dag.json" ]] || return 1
    [[ -f "${output_dir}/architecting_structure.json" ]] || return 1
    [[ -f "${output_dir}/contracting_implementation_contract.json" ]] || return 1
    [[ -f "${output_dir}/unified_engineering_index.json" ]] || return 1
    has_eval_artifact "${output_dir}/eval" "${paper_name}" "ref_free" || return 1
    has_eval_artifact "${output_dir}/eval" "${paper_name}" "ref_based" || return 1
    return 0
}

append_run_index() {
    local paper_name="$1"
    local status="$2"
    local exit_code="$3"
    local duration="$4"
    printf '%s\n' "$("${PYTHON_BIN}" - <<PY
import json
print(json.dumps({
    "paper_name": "${paper_name}",
    "pipeline": "${PIPELINE}",
    "run": 1,
    "status": "${status}",
    "exit_code": ${exit_code},
    "duration_sec": ${duration}
}))
PY
)" >> "${RUN_INDEX}"
}

collect_stats() {
    "${PYTHON_BIN}" - "${BATCH_ROOT}" "${RUN_INDEX}" "${STATS_CSV}" "${STATS_JSON}" "${SUMMARY_TXT}" "${EVAL_MODEL}" "${CURRENT_CONFERENCE}" <<'PY'
import csv
import json
import re
import sys
from pathlib import Path

batch_root = Path(sys.argv[1])
run_index = Path(sys.argv[2])
csv_path = Path(sys.argv[3])
json_path = Path(sys.argv[4])
summary_path = Path(sys.argv[5])
eval_model = sys.argv[6]
conference = sys.argv[7]

rows_by_paper = {}
if run_index.exists():
    for line in run_index.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        paper = item.get("paper_name")
        if paper:
            rows_by_paper[paper] = {
                "paper_name": paper,
                "pipeline": item.get("pipeline", "papercompiler_o3mini"),
                "run": item.get("run", 1),
                "status": item.get("status", ""),
                "exit_code": item.get("exit_code", ""),
                "duration_sec": item.get("duration_sec", ""),
                "gpt_version": eval_model,
            }

eval_pattern = re.compile(r"_eval_(ref_free|ref_based)_.*\.json$")
for eval_json in sorted(batch_root.rglob("*_eval_*.json")):
    if eval_json.name.endswith("_parsed.json"):
        continue
    if not eval_pattern.search(eval_json.name):
        continue
    try:
        obj = json.loads(eval_json.read_text(encoding="utf-8"))
    except Exception:
        continue
    if obj.get("gpt_version") != eval_model:
        continue
    paper_name = obj.get("paper_name")
    eval_type = obj.get("eval_type")
    if not paper_name or eval_type not in ("ref_free", "ref_based"):
        continue
    result = obj.get("eval_result", {})
    row = rows_by_paper.setdefault(
        paper_name,
        {
            "paper_name": paper_name,
            "pipeline": "papercompiler_o3mini",
            "run": 1,
            "status": "",
            "exit_code": "",
            "duration_sec": "",
            "gpt_version": eval_model,
        },
    )
    row[f"{eval_type}_score"] = result.get("score")
    row[f"{eval_type}_valid_n"] = result.get("valid_n")

table_rows = [rows_by_paper[k] for k in sorted(rows_by_paper)]
fieldnames = [
    "paper_name",
    "pipeline",
    "run",
    "status",
    "exit_code",
    "duration_sec",
    "gpt_version",
    "ref_free_score",
    "ref_free_valid_n",
    "ref_based_score",
    "ref_based_valid_n",
]

csv_path.parent.mkdir(parents=True, exist_ok=True)
with csv_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in table_rows:
        writer.writerow({k: row.get(k, "") for k in fieldnames})

json_path.write_text(
    json.dumps({"rows": table_rows, "row_count": len(table_rows)}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

summary_lines = [
    f"=== {conference.upper()} PaperCompiler summary ===",
    f"papers: {len(table_rows)}",
    "",
]
ok_count = 0
for row in table_rows:
    if row.get("status") == "success":
        ok_count += 1
    summary_lines.append(
        f"{row.get('paper_name','')} | status={row.get('status','')} | "
        f"free={row.get('ref_free_score','')}({row.get('ref_free_valid_n','')}) | "
        f"based={row.get('ref_based_score','')}({row.get('ref_based_valid_n','')}) | "
        f"dur={row.get('duration_sec','')}s"
    )
summary_lines.append("")
summary_lines.append(f"success={ok_count}/{len(table_rows)}")

summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
print(summary_path.read_text(encoding="utf-8"))
print(f"Wrote stats csv: {csv_path}")
print(f"Wrote stats json: {json_path}")
PY
}

configure_conference_paths() {
    local conference="$1"
    CURRENT_CONFERENCE="${conference}"
    PAPER_DIR="${DATA_ROOT}/${conference}"
    BATCH_ROOT="${OUTPUTS_ROOT}/batch_${conference}_papercompiler_o3mini"
    RUN_INDEX="${BATCH_ROOT}/run_index.jsonl"
    RUN_LOG="${BATCH_ROOT}/batch_run.log"
    STATS_CSV="${BATCH_ROOT}/batch_stats.csv"
    STATS_JSON="${BATCH_ROOT}/batch_stats.json"
    SUMMARY_TXT="${BATCH_ROOT}/batch_summary.txt"
    mkdir -p "${BATCH_ROOT}"
    touch "${RUN_INDEX}"
}

conference_is_complete() {
    local -n _paper_files_ref=$1
    local paper_input paper_name output_dir repo_dir gold_repo

    for paper_input in "${_paper_files_ref[@]}"; do
        paper_name="$(paper_name_from_input "${paper_input}")"
        output_dir="${BATCH_ROOT}/${paper_name}"
        repo_dir="${BATCH_ROOT}/${paper_name}_repo"
        gold_repo="${GOLD_REPO_BASE}/${paper_name}"
        if [[ ! -d "${gold_repo}" ]]; then
            return 1
        fi
        if ! is_run_complete "${paper_name}" "${output_dir}" "${repo_dir}"; then
            return 1
        fi
    done
    return 0
}

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] WARNING: OPENAI_API_KEY is not set. PaperCompiler/eval may fail."
fi

for conference in ${CONFERENCES}; do
    configure_conference_paths "${conference}"
    if [[ ! -d "${PAPER_DIR}" ]]; then
        log "SKIP conference ${conference}: paper dir missing (${PAPER_DIR})"
        continue
    fi
    mapfile -t PAPER_FILES < <(find "${PAPER_DIR}" -maxdepth 1 -type f -name '*_cleaned.json' | sort)
    CURRENT_PAPER_FORMAT="JSON"
    if [[ ${#PAPER_FILES[@]} -eq 0 ]]; then
        mapfile -t PAPER_FILES < <(find "${PAPER_DIR}" -maxdepth 1 -type f -name '*.pdf' | sort)
        CURRENT_PAPER_FORMAT="Markdown"
    fi
    if [[ ${#PAPER_FILES[@]} -eq 0 ]]; then
        log "ERROR: No *_cleaned.json or PDF inputs found in ${PAPER_DIR}"
        continue
    fi

    if [[ "${FORCE_RERUN}" != "1" ]] && conference_is_complete PAPER_FILES; then
        log "SKIP conference ${conference}: already complete"
        continue
    fi

    log "Conference: ${conference}"
    log "Batch root: ${BATCH_ROOT}"
    log "Pipeline: PaperCompiler full workflow"
    log "Model: pipeline=${GPT_VERSION}, eval=${EVAL_MODEL}"
    log "Input format: ${CURRENT_PAPER_FORMAT}"
    log "Papers: ${#PAPER_FILES[@]} (each paper runs once)"
    log "Resume: enabled (FORCE_RERUN=${FORCE_RERUN})"

    for paper_input_path in "${PAPER_FILES[@]}"; do
        paper_name="$(paper_name_from_input "${paper_input_path}")"
        output_dir="${BATCH_ROOT}/${paper_name}"
        repo_dir="${BATCH_ROOT}/${paper_name}_repo"
        gold_repo="${GOLD_REPO_BASE}/${paper_name}"
        mkdir -p "${output_dir}" "${repo_dir}"

        if [[ ! -d "${gold_repo}" ]]; then
            log "SKIP ${paper_name}: gold repo missing"
            append_run_index "${paper_name}" "skipped_no_gold" 2 0
            collect_stats
            continue
        fi

        if [[ "${FORCE_RERUN}" != "1" ]] && is_run_complete "${paper_name}" "${output_dir}" "${repo_dir}"; then
            log "SKIP ${paper_name}: already complete"
            continue
        fi

        log "START ${paper_name}"
        start_ts="$(date +%s)"
        set +e
        (
            cd "${SCRIPT_DIR}"
            export PAPER_NAME="${paper_name}"
            export PAPER_DIR_OVERRIDE="${PAPER_DIR}"
            export PAPER_FORMAT="${CURRENT_PAPER_FORMAT}"
            export PAPER_INPUT_PATH_OVERRIDE="${paper_input_path}"
            if [[ "${CURRENT_PAPER_FORMAT}" == "Markdown" ]]; then
                export PDF_PATH_OVERRIDE="${paper_input_path}"
            fi
            export OUTPUT_DIR_OVERRIDE="${output_dir}"
            export OUTPUT_REPO_DIR_OVERRIDE="${repo_dir}"
            export GOLD_REPO_DIR_OVERRIDE="${gold_repo}"
            export GPT_VERSION="${GPT_VERSION}"
            export EVAL_MODEL="${EVAL_MODEL}"
            export GENERATED_N="${GENERATED_N}"
            unset SKIP_EVAL
            bash "${RUN_SCRIPT}"
        )
        exit_code=$?
        set -e
        end_ts="$(date +%s)"
        duration=$((end_ts - start_ts))

        status="success"
        if [[ ${exit_code} -ne 0 ]]; then
            status="failed"
        fi

        log "END ${paper_name}: ${status} exit=${exit_code} duration=${duration}s"
        append_run_index "${paper_name}" "${status}" "${exit_code}" "${duration}"
        collect_stats
    done

    collect_stats
    log "=== Conference ${conference} finished ==="
    log "Stats csv: ${STATS_CSV}"
    log "Stats json: ${STATS_JSON}"
    log "Summary: ${SUMMARY_TXT}"
done

log "=== Batch finished ==="
