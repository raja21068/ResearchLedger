"""The results contract: empty slots in the first draft, filled by code.

The first draft of the paper is written BEFORE any experiment runs. Every number a
result table would hold is a slot, `\\PFVAL{id}`, and every results figure is a slot,
`\\PFFIG{id}`; `results_spec.json` lists them. Until results exist a slot renders as a
bold "TBD" or a framed "Figure pending" box, so the draft compiles and reads as a
template with empty tables and empty plots.

That draft is the requirement document for the code step: its tables and figures say
exactly which numbers the experiments must produce. The sandbox run writes
`results.json` against the same ids, and this module then fills the paper:

  * `pf_results.tex` defines the value of each id (the macros read it), and
  * figures are drawn from the measured series.

Numbers reach the manuscript through this code and nowhere else, so none of them is
typed by a model.
"""
import json
import pathlib
import re

SLOT_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{1,60}$")
MARKER = "% PF-PLACEHOLDER-MACROS"
MAX_RESULTS_BYTES = 32 * 1024 * 1024
MAX_PLOT_POINTS = 50_000
MAX_CURVES = 32

MACROS = MARKER + r"""
\IfFileExists{pf_results.tex}{\input{pf_results.tex}}{}
\newcommand{\PFVAL}[1]{\ifcsname pfval@#1\endcsname\csname pfval@#1\endcsname\else\textbf{TBD}\fi}
\newcommand{\PFFIG}[1]{\IfFileExists{figures/#1.pdf}{\includegraphics[width=0.9\linewidth]{figures/#1.pdf}}{\fbox{\parbox[c][6em][c]{0.85\linewidth}{\centering\textit{Figure pending:} \texttt{\detokenize{#1}}}}}}
"""

USED = re.compile(r"\\PF(VAL|FIG)\{([^{}]+)\}")


def validate_spec(spec):
    """Problems with a results spec, as a list of strings (empty means valid)."""
    if not isinstance(spec, dict) or not isinstance(spec.get("slots"), list) or not spec["slots"]:
        return ["results spec needs a non-empty 'slots' list"]
    problems, seen = [], set()
    for slot in spec["slots"]:
        slot_id = slot.get("id") if isinstance(slot, dict) else None
        if not isinstance(slot_id, str) or not SLOT_ID.match(slot_id):
            problems.append(f"bad slot id {slot_id!r}: letters, digits, _ . - only, start with a letter")
            continue
        if slot_id in seen:
            problems.append(f"duplicate slot id {slot_id}")
        seen.add(slot_id)
        if "optional" in slot and not isinstance(slot["optional"], bool):
            problems.append(f"{slot_id}: optional must be boolean")
        if slot.get("kind") == "series" and slot.get("plot", "line") not in ("line", "bar"):
            problems.append(f"{slot_id}: plot must be line or bar")
        if slot.get("kind") not in ("value", "series"):
            problems.append(f"{slot_id}: kind must be 'value' or 'series'")
        if not str(slot.get("describe", "")).strip():
            problems.append(f"{slot_id}: describe what it measures")
    return problems


def load_spec(path):
    try:
        spec = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"results spec missing or invalid: {exc}") from exc
    problems = validate_spec(spec)
    if problems:
        raise ValueError("; ".join(problems))
    return spec


def ensure_macros(tex):
    """Add the placeholder macros before \\begin{document} if the draft lacks them."""
    if MARKER in tex:
        return tex
    block = MACROS
    if "graphicx" not in tex:
        block = "\\usepackage{graphicx}\n" + block
    if "\\begin{document}" not in tex:
        raise ValueError("paper.tex has no \\begin{document}")
    return tex.replace("\\begin{document}", block + "\\begin{document}", 1)


def used_slots(tex):
    """{'value': {...ids}, 'series': {...ids}} as used in the draft."""
    found = {"value": set(), "series": set()}
    for kind, slot_id in USED.findall(tex):
        found["value" if kind == "VAL" else "series"].add(slot_id)
    return found


def coverage_problems(tex, spec):
    """Slots the draft forgot, and slot ids the draft invented."""
    by_kind = {"value": set(), "series": set()}
    for slot in spec["slots"]:
        by_kind[slot["kind"]].add(slot["id"])
    used = used_slots(tex)
    problems = []
    for kind, label in (("value", "\\PFVAL"), ("series", "\\PFFIG")):
        missing = sorted(by_kind[kind] - used[kind])
        extra = sorted(used[kind] - by_kind[kind])
        if missing:
            problems.append(f"{label} slots in the spec but not in the paper: {', '.join(missing)}")
        if extra:
            problems.append(f"{label} ids in the paper but not in the spec: {', '.join(extra)}")
    return problems


# -- results.json ------------------------------------------------------------

def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value \
        and value not in (float("inf"), float("-inf"))


def read_results(path):
    """A validated results payload, or ValueError saying what is wrong with it."""
    try:
        source = pathlib.Path(path)
        if source.stat().st_size > MAX_RESULTS_BYTES:
            raise ValueError("results.json exceeds the 32 MiB safety limit")
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"results.json missing or invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("results.json must be an object")
    values, series = payload.get("values") or {}, payload.get("series") or {}
    if not isinstance(values, dict) or not isinstance(series, dict) or not (values or series):
        raise ValueError("results.json needs 'values' and/or 'series'")
    ids = [key for key in (*values.keys(), *series.keys())
           if not isinstance(key, str) or not SLOT_ID.fullmatch(key)]
    if ids:
        raise ValueError(f"results contain invalid slot ids: {ids!r}")
    bad = [k for k, v in values.items() if not _is_number(v)]
    if bad:
        raise ValueError("non-numeric values: " + ", ".join(bad))
    for key, item in series.items():
        names = item.get("series") if isinstance(item, dict) else None
        x = item.get("x") if isinstance(item, dict) else None
        if not isinstance(x, list) or not x or not isinstance(names, dict) or not names:
            raise ValueError(f"series {key} needs 'x' and a non-empty 'series' object")
        if len(x) > MAX_PLOT_POINTS or len(names) > MAX_CURVES:
            raise ValueError(f"series {key} exceeds the plot size limit")
        if not (all(_is_number(point) for point in x) or
                all(isinstance(point, str) and bool(point.strip()) for point in x)):
            raise ValueError(f"series {key} x-axis must contain finite numbers or labels")
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError(f"series {key} names must be non-empty strings")
        for name, ys in names.items():
            if not isinstance(ys, list) or len(ys) != len(x) or not all(_is_number(y) for y in ys):
                raise ValueError(f"series {key}/{name} must be numbers, one per x value")
    return payload


def missing_slots(spec, payload):
    """Spec slots the results do not cover (optional slots are not required)."""
    missing = []
    for slot in spec["slots"]:
        if slot.get("optional"):
            continue
        have = payload.get("values") if slot["kind"] == "value" else payload.get("series")
        if slot["id"] not in (have or {}):
            missing.append(slot["id"])
    return missing


# -- filling the paper -------------------------------------------------------

def format_value(value):
    """A number as LaTeX text. Large and small values are not left in raw exponent form."""
    if isinstance(value, int):
        return str(value)
    text = format(value, ".4g")
    if "e" in text:
        mantissa, exponent = text.split("e")
        return f"${mantissa}\\times10^{{{int(exponent)}}}$"
    return text


def write_values_tex(build_dir, payload):
    lines = [f"\\expandafter\\def\\csname pfval@{key}\\endcsname{{{format_value(value)}}}"
             for key, value in sorted((payload.get("values") or {}).items())]
    path = pathlib.Path(build_dir) / "pf_results.tex"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def plot_series(build_dir, spec, payload):
    """Draw each measured series to figures/<id>.pdf. Returns (drawn ids, warning or None)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return [], "matplotlib is not installed; figures were left as placeholders"
    figures = pathlib.Path(build_dir) / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    meta = {slot["id"]: slot for slot in spec["slots"] if slot["kind"] == "series"}
    drawn = []
    for key, item in (payload.get("series") or {}).items():
        slot = meta.get(key, {})
        kind = slot.get("plot", "line")
        fig, ax = plt.subplots(figsize=(5.2, 3.4))
        x = item["x"]
        names = list(item["series"])
        if kind == "bar":
            width = 0.8 / len(names)
            for i, name in enumerate(names):
                ax.bar([j + i * width for j in range(len(x))], item["series"][name], width, label=name)
            ax.set_xticks([j + 0.4 - width / 2 for j in range(len(x))])
            ax.set_xticklabels([str(v) for v in x])
        else:
            for name in names:
                ax.plot(x, item["series"][name], marker="o", label=name)
        ax.set_xlabel(slot.get("x_label", ""))
        ax.set_ylabel(slot.get("y_label", ""))
        if len(names) > 1:
            ax.legend()
        fig.tight_layout()
        fig.savefig(figures / f"{key}.pdf")
        plt.close(fig)
        drawn.append(key)
    return drawn, None


def fill(build_dir, spec, payload):
    """Write the values file and the figures into a paper build directory."""
    write_values_tex(build_dir, payload)
    drawn, warning = plot_series(build_dir, spec, payload)
    required = {s["id"] for s in spec["slots"] if s["kind"] == "series" and not s.get("optional")}
    if warning and required:
        raise ValueError(f"cannot fill required figures: {warning}")
    if required - set(drawn):
        raise ValueError("required figures were not generated: " + ", ".join(sorted(required - set(drawn))))
    return {"values": len(payload.get("values") or {}), "figures": drawn, "warning": warning}
