<div align="center">

# PaperCompiler


**[Yunhao Liu](https://github.com/Daethalous)**<sup>1</sup>, **[Hong Phuc Pham](https://github.com/PhamHongPhuc2712)**<sup>1</sup>, **[Jaehong Yoon](https://jaehong31.github.io/)**<sup>1,&dagger;</sup>

<sup>1</sup>NTU Singapore

<sup>&dagger;</sup>Corresponding author

[![arXiv](https://img.shields.io/badge/arXiv-2609.02272-b31b1b.svg)](https://arxiv.org/abs/2609.02272)

PaperCompiler converts a machine learning paper into an implementation blueprint, reference registry, implementation constraints, project architecture, per-file contracts, and a generated code repository. This directory contains only the generation and evaluation code required for the final Paper2Code Benchmark experiments.

</div>

## Requirements

- Python 3.10 or later
- Bash
- An OpenAI API key for actual generation and evaluation
- MinerU only when using PDF input

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="<OPENAI_API_KEY>"
```

## Experiment inputs

The 90 papers, parsed paper files, and author repositories are not distributed in this directory. Obtain the Paper2Code Benchmark from:

- [PaperCoder/Paper2Code repository](https://github.com/going-doer/Paper2Code)
- [Paper2Code Benchmark directory](https://github.com/going-doer/Paper2Code/tree/main/data/paper2code)
- [Paper2Code dataset on Hugging Face](https://huggingface.co/datasets/iaminju/paper2code)

Extract the benchmark to `data/paper2code`, or set `DATA_ROOT` to an external directory. Batch experiments prefer the `*_cleaned.json` files in each conference directory:

```text
data/paper2code/
├── iclr2024/
├── icml2024/
└── nips2024/
```

Gold repositories are not included. Place each author repository at `gold_repos/<paper_name>`, or set `GOLD_REPO_BASE` to an external directory. Repository URLs are available in the benchmark's `dataset_info.json`.

## Single-paper experiment

JSON input:

```bash
PAPER_NAME=iTransformer \
PAPER_FORMAT=JSON \
PAPER_INPUT_PATH_OVERRIDE=/path/to/iTransformer_cleaned.json \
bash scripts/run.sh
```

Markdown input:

```bash
PAPER_NAME=iTransformer \
PAPER_FORMAT=Markdown \
PAPER_MARKDOWN_PATH_OVERRIDE=/path/to/iTransformer.md \
bash scripts/run.sh
```

For PDF input, use `PAPER_FORMAT=Markdown` and set `PDF_PATH_OVERRIDE`; the script invokes MinerU to produce Markdown. Set `SKIP_EVAL=1` to run code generation without evaluation. If the matching gold repository is unavailable, the single-paper workflow performs reference-free evaluation and skips reference-based evaluation.

## Batch experiment on 90 papers

```bash
DATA_ROOT=/path/to/paper2code \
GOLD_REPO_BASE=/path/to/gold_repos \
bash scripts/run_batch.sh
```

The default conference sequence is `iclr2024 icml2024 nips2024`. Configuration variables:

- `CONFERENCES`: space-separated conference list.
- `GPT_VERSION`: generation model; default: `o3-mini`.
- `EVAL_MODEL`: evaluation model; default: `o3-mini`.
- `GENERATED_N`: samples per evaluation type; default: `8`.
- `OUTPUTS_ROOT`: output root; default: `outputs`.
- `FORCE_RERUN=1`: ignore completion markers and rerun experiments.

The batch runner supports checkpoint-based resumption and writes `batch_stats.csv`, `batch_stats.json`, and `batch_summary.txt` for each conference. Papers without matching gold repositories are skipped.

## API-free validation

The dry run validates the selected input, required pipeline files, evaluation prompts, and resolved output paths without reading `OPENAI_API_KEY`, creating outputs, or making API calls:

```bash
env -u OPENAI_API_KEY \
PAPER_NAME=example \
PAPER_FORMAT=Markdown \
PAPER_MARKDOWN_PATH_OVERRIDE=/path/to/paper.md \
DRY_RUN=1 \
bash scripts/run.sh
```

Static checks:

```bash
python -c "from pathlib import Path; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in Path('codes').glob('*.py')]"
bash -n scripts/run.sh scripts/run_batch.sh
```

## Directory layout

```text
papercompiler/
├── codes/                 # PaperCompiler stages and evaluation
├── data/prompts/          # Reference-free and reference-based prompts
├── scripts/run.sh         # Single-paper entry point
├── scripts/run_batch.sh   # 90-paper batch entry point
└── requirements.txt
```

Runtime artifacts are written to `outputs/` by default. The directory is excluded by `.gitignore`.

## Citation

If you find PaperCompiler useful in your research, please consider citing our work:

```bibtex
@article{liu2026papercompiler,
  title   = {PaperCompiler: Faithful Paper-to-Code Generation via Repository-Level Specification Compilation},
  author  = {Liu, Yunhao and Pham, Hong Phuc and Yoon, Jaehong},
  journal = {arXiv preprint arXiv:2609.02272},
  year    = {2026}
}
```
