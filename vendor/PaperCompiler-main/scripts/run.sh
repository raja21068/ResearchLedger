#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

GPT_VERSION="${GPT_VERSION:-o3-mini}"
REASONING_EFFORT="${REASONING_EFFORT:-high}"
EVAL_MODEL="${EVAL_MODEL:-o3-mini}"
GENERATED_N="${GENERATED_N:-8}"

PAPER_NAME="${PAPER_NAME:-iTransformer}"
DATA_ROOT="${DATA_ROOT:-${ROOT}/data/paper2code}"
PAPER_DIR="${PAPER_DIR_OVERRIDE:-${DATA_ROOT}/iclr2024}"
PAPER_FORMAT="${PAPER_FORMAT:-JSON}"
PDF_PATH="${PDF_PATH_OVERRIDE:-${PAPER_DIR}/${PAPER_NAME}.pdf}"
PDF_MARKDOWN_PATH="${PAPER_MARKDOWN_PATH_OVERRIDE:-${PAPER_DIR}/${PAPER_NAME}/hybrid_auto/${PAPER_NAME}.md}"
PAPER_INPUT_PATH="${PAPER_INPUT_PATH_OVERRIDE:-${PAPER_DIR}/${PAPER_NAME}_cleaned.json}"
OUTPUTS_ROOT="${OUTPUTS_ROOT:-${ROOT}/outputs}"
if [[ -n "${OUTPUT_DIR_OVERRIDE:-}" ]]; then
    OUTPUT_DIR="${OUTPUT_DIR_OVERRIDE}"
    OUTPUT_REPO_DIR="${OUTPUT_REPO_DIR_OVERRIDE:-${OUTPUT_DIR_OVERRIDE}_repo}"
else
    RUN_TAG=""
    if [[ -n "${RUN_ID:-}" ]]; then
        RUN_TAG="_run${RUN_ID}"
    fi
    OUTPUT_DIR="${OUTPUTS_ROOT}/${PAPER_NAME}${RUN_TAG}"
    OUTPUT_REPO_DIR="${OUTPUTS_ROOT}/${PAPER_NAME}_repo${RUN_TAG}"
fi
DATA_DIR="${ROOT}/data"
GOLD_REPO_BASE="${GOLD_REPO_BASE:-${ROOT}/gold_repos}"
GOLD_REPO_DIR="${GOLD_REPO_DIR_OVERRIDE:-${GOLD_REPO_BASE}/${PAPER_NAME}}"
EVAL_RESULT_DIR="${OUTPUT_DIR}/eval"

PAPER_REFERENCE_ARGS=()
if [[ "${PAPER_FORMAT}" == "JSON" ]]; then
    if [[ ! -f "${PAPER_INPUT_PATH}" ]]; then
        echo "Error: JSON input not found at ${PAPER_INPUT_PATH}" >&2
        exit 1
    fi
    PAPER_REFERENCE_ARGS=(--paper_format JSON --pdf_json_path "${PAPER_INPUT_PATH}")
elif [[ "${PAPER_FORMAT}" == "LaTeX" ]]; then
    if [[ ! -f "${PAPER_INPUT_PATH}" ]]; then
        echo "Error: LaTeX input not found at ${PAPER_INPUT_PATH}" >&2
        exit 1
    fi
    PAPER_REFERENCE_ARGS=(--paper_format LaTeX --pdf_latex_path "${PAPER_INPUT_PATH}")
elif [[ "${PAPER_FORMAT}" == "Markdown" && ! -f "${PDF_MARKDOWN_PATH}" ]]; then
    if [[ ! -f "${PDF_PATH}" ]]; then
        echo "Error: neither parsed Markdown nor PDF input was found." >&2
        echo "Markdown: ${PDF_MARKDOWN_PATH}" >&2
        echo "PDF: ${PDF_PATH}" >&2
        exit 1
    fi
    if ! command -v mineru >/dev/null 2>&1; then
        echo "Error: mineru is required to parse PDF input." >&2
        exit 127
    fi
    echo "------- MinerU parsing -------"
    mineru -p "${PDF_PATH}" -o "${PAPER_DIR}"
    if [[ ! -f "${PDF_MARKDOWN_PATH}" ]]; then
        echo "Error: Parsed markdown not found at ${PDF_MARKDOWN_PATH}" >&2
        exit 1
    fi
else
    echo "------- MinerU: using existing parsed markdown -------"
fi
if [[ "${PAPER_FORMAT}" == "Markdown" ]]; then
    PAPER_REFERENCE_ARGS=(--paper_format Markdown --pdf_markdown_path "${PDF_MARKDOWN_PATH}")
elif [[ "${PAPER_FORMAT}" != "JSON" && "${PAPER_FORMAT}" != "LaTeX" ]]; then
    echo "Error: PAPER_FORMAT must be JSON, Markdown, or LaTeX." >&2
    exit 2
fi

REQUIRED_FILES=(
    "${ROOT}/codes/1_translating.py"
    "${ROOT}/codes/1_5_reference_extraction.py"
    "${ROOT}/codes/2_reconciling.py"
    "${ROOT}/codes/3_architecting.py"
    "${ROOT}/codes/3_5_info_seperating.py"
    "${ROOT}/codes/4_contracting.py"
    "${ROOT}/codes/5_engineering.py"
    "${ROOT}/codes/eval.py"
    "${ROOT}/codes/utils.py"
    "${ROOT}/data/prompts/ref_free.txt"
    "${ROOT}/data/prompts/ref_based.txt"
)
for required_file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "${required_file}" ]]; then
        echo "Error: required file not found at ${required_file}" >&2
        exit 1
    fi
done

if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "PaperCompiler dry run passed."
    echo "Paper: ${PAPER_NAME}"
    echo "Format: ${PAPER_FORMAT}"
    echo "Input: ${PAPER_REFERENCE_ARGS[*]}"
    echo "Artifacts: ${OUTPUT_DIR}"
    echo "Repository: ${OUTPUT_REPO_DIR}"
    exit 0
fi

mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_REPO_DIR"
mkdir -p "$EVAL_RESULT_DIR"

echo "$PAPER_NAME"

echo "------- PaperCompiler -------"

python "${ROOT}/codes/1_translating.py" \
    --paper_name "$PAPER_NAME" \
    --gpt_version "${GPT_VERSION}" \
    "${PAPER_REFERENCE_ARGS[@]}" \
    --output_dir "${OUTPUT_DIR}"

python "${ROOT}/codes/1_5_reference_extraction.py" \
    --paper_name "$PAPER_NAME" \
    --gpt_version "${GPT_VERSION}" \
    "${PAPER_REFERENCE_ARGS[@]}" \
    --output_dir "${OUTPUT_DIR}" \
    --s1_blueprint_path "${OUTPUT_DIR}/translating_blueprint.txt"

python "${ROOT}/codes/2_reconciling.py" \
    --paper_name "$PAPER_NAME" \
    --gpt_version "${GPT_VERSION}" \
    "${PAPER_REFERENCE_ARGS[@]}" \
    --output_dir "${OUTPUT_DIR}" \
    --translating_blueprint_path "${OUTPUT_DIR}/translating_blueprint.txt"
cp -f "${OUTPUT_DIR}/reconciling_spec.json" "${OUTPUT_DIR}/reconciling_dag.json"

python "${ROOT}/codes/3_architecting.py" \
    --paper_name "$PAPER_NAME" \
    --gpt_version "${GPT_VERSION}" \
    "${PAPER_REFERENCE_ARGS[@]}" \
    --output_dir "${OUTPUT_DIR}" \
    --translating_blueprint_path "${OUTPUT_DIR}/translating_blueprint.txt" \
    --reconciling_spec_path "${OUTPUT_DIR}/reconciling_spec.json"
cp -f "${OUTPUT_DIR}/architecting_plan.json" "${OUTPUT_DIR}/architecting_structure.json"

# Stage 3.5 preprocess: build compact contracting contexts.
python "${ROOT}/codes/3_5_info_seperating.py" \
    --output_dir "${OUTPUT_DIR}" \
    --reconciling_spec_path "${OUTPUT_DIR}/reconciling_spec.json" \
    --architecting_plan_path "${OUTPUT_DIR}/architecting_plan.json" \
    --translating_blueprint_path "${OUTPUT_DIR}/translating_blueprint.txt" \
    --preprocess_subdir info_seperating_inputs \
    --use_generation_order

# Stage 4: implementation contract contracting (no paper args; uses S3.5 compact contexts only).
python "${ROOT}/codes/4_contracting.py" \
    --paper_name "$PAPER_NAME" \
    --gpt_version "${GPT_VERSION}" \
    --reasoning_effort "${REASONING_EFFORT}" \
    --output_dir "${OUTPUT_DIR}" \
    --preprocess_dir "${OUTPUT_DIR}/info_seperating_inputs" \
    --artifact_subdir contracting_artifacts

# Stage 5: full-file sequential engineering with prior code context.
ENGINEERING_ARGS=(
    --paper_name "$PAPER_NAME"
    --gpt_version "${GPT_VERSION}"
    "${PAPER_REFERENCE_ARGS[@]}"
    --output_dir "${OUTPUT_DIR}"
    --output_repo_dir "${OUTPUT_REPO_DIR}"
    --translating_blueprint_path "${OUTPUT_DIR}/translating_blueprint.txt"
    --reconciling_dag_path "${OUTPUT_DIR}/reconciling_dag.json"
    --architecting_structure_path "${OUTPUT_DIR}/architecting_structure.json"
    --contracting_contract_path "${OUTPUT_DIR}/contracting_implementation_contract.json"
    --reference_registry_path "${OUTPUT_DIR}/reference_registry.json"
)
python "${ROOT}/codes/5_engineering.py" "${ENGINEERING_ARGS[@]}"

if [[ -z "${SKIP_EVAL:-}" ]]; then
echo "------- Evaluation -------"

python "${ROOT}/codes/eval.py" \
    --paper_name "$PAPER_NAME" \
    "${PAPER_REFERENCE_ARGS[@]}" \
    --data_dir "${DATA_DIR}" \
    --output_dir "${OUTPUT_DIR}" \
    --target_repo_dir "${OUTPUT_REPO_DIR}" \
    --gold_repo_dir "${GOLD_REPO_DIR}" \
    --eval_result_dir "${EVAL_RESULT_DIR}" \
    --eval_type ref_free \
    --generated_n "${GENERATED_N}" \
    --gpt_version "${EVAL_MODEL}"

if [[ -d "${GOLD_REPO_DIR}" ]]; then
python "${ROOT}/codes/eval.py" \
    --paper_name "$PAPER_NAME" \
    "${PAPER_REFERENCE_ARGS[@]}" \
    --data_dir "${DATA_DIR}" \
    --output_dir "${OUTPUT_DIR}" \
    --target_repo_dir "${OUTPUT_REPO_DIR}" \
    --gold_repo_dir "${GOLD_REPO_DIR}" \
    --eval_result_dir "${EVAL_RESULT_DIR}" \
    --eval_type ref_based \
    --generated_n "${GENERATED_N}" \
    --gpt_version "${EVAL_MODEL}"
else
    echo "------- Reference-based evaluation skipped: gold repository not found -------"
    echo "${GOLD_REPO_DIR}"
fi
fi
