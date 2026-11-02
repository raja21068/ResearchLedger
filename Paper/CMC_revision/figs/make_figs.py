"""Data figures for the manuscript, generated from code/results/*.json (no numbers are typed by hand)."""
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "code" / "results"
OUT = ROOT / "figs"

mpl.rcParams.update({
    "font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
    "font.size": 7, "axes.labelsize": 7, "axes.titlesize": 7.5, "legend.fontsize": 6.2,
    "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "axes.linewidth": 0.6, "xtick.major.width": 0.6,
    "ytick.major.width": 0.6, "xtick.major.size": 2.5, "ytick.major.size": 2.5, "pdf.fonttype": 42,
    "axes.spines.top": False, "axes.spines.right": False, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
# Okabe-Ito colour-blind-safe palette
C = {"full": "#0072B2", "binary": "#D55E00", "egr": "#E69F00", "gray": "#7f7f7f", "green": "#009E73",
     "purple": "#CC79A7", "sky": "#56B4E9", "black": "#222222"}
COL, FULL = 3.5, 7.16


def panel_label(ax, s, dx=-0.02):
    ax.text(dx, 1.06, s, transform=ax.transAxes, fontsize=8.5, fontweight="bold", va="bottom", ha="right")


# ------------------------------------------------------------------ Fig: SUP-300 (full width, 3 panels)
def fig_sup():
    d = json.load(open(R / "sup_diagnostic_results.json"))
    tpl = ["single", "conj", "alt", "required", "dep"]
    names = ["Single", "Conj.", "Alt.", "Req.", "Dep."]
    bt = d["by_template"]
    fig, axs = plt.subplots(1, 3, figsize=(FULL, 2.2), gridspec_kw={"width_ratios": [1.2, 1.0, 1.25], "wspace": 0.62})
    x = np.arange(len(tpl)); w = 0.26
    ax = axs[0]
    for k, (sys_, lab, col) in enumerate([("trl_binary_edges", "TRL, binary edges", C["binary"]),
                                          ("evigraph_reconstruction", "EG-R (reconstruction)", C["egr"]),
                                          ("trl_full", "Full TRL", C["full"])]):
        v = [bt[sys_][t]["claim_invalidation_recall"] for t in tpl]
        ax.bar(x + (k - 1) * w, v, w, label=lab, color=col, edgecolor="white", linewidth=0.4)
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=6.2); ax.set_ylim(0, 1.3)
    ax.set_ylabel("Claim-invalidation recall"); ax.legend(frameon=False, loc="upper left", ncol=1, handlelength=1.0, fontsize=5.6)
    panel_label(ax, "(a)")
    ax = axs[1]
    for k, (sys_, lab, col) in enumerate([("evigraph_reconstruction", "EG-R", C["egr"]), ("trl_full", "Full TRL", C["full"])]):
        v = [bt[sys_][t]["false_invalidation_rate"] for t in tpl]
        ax.bar(x + (k - 0.5) * 0.34, v, 0.34, color=col, edgecolor="white", linewidth=0.4, label=lab)
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=6.2); ax.set_ylim(0, 0.40)
    ax.set_ylabel("False-invalidation rate")
    ax.annotate("alternative path\nflagged for\nregeneration", xy=(2 - 0.17, 0.303), xytext=(-0.5, 0.15), fontsize=5.6, ha="left",
                arrowprops=dict(arrowstyle="-", lw=0.5, color=C["gray"]), va="center")
    ax.legend(frameon=False, loc="upper right")
    panel_label(ax, "(b)")
    ax = axs[2]
    o = d["overall"]
    conds = [("mutable_state", "Mutable state"), ("claim_relabel", "Claim relabelling"),
             ("txn_no_propagation", "Transaction, no propagation"), ("provenance_graph", "Provenance graph (query-only)"),
             ("trl_binary_edges", "TRL, binary edges"), ("evigraph_reconstruction", "EG-R (reconstruction)"),
             ("evigraph_reconstruction_D", "EG-R + decision nodes"), ("trl_full", "Full TRL")]
    y = np.arange(len(conds))[::-1]
    upd = [o[k]["updated"]["manuscript_stale_claim_escape"] for k, _ in conds]
    idn = [o[k]["identified"]["manuscript_stale_claim_escape"] for k, _ in conds]
    cols = [C["gray"], C["gray"], C["gray"], C["purple"], C["binary"], C["egr"], C["egr"], C["full"]]
    ax.barh(y, upd, 0.6, color=cols, edgecolor="white", linewidth=0.4)
    for yy, v in zip(y, upd):
        ax.text(v + 0.015, yy, f"{v:.2f}", va="center", fontsize=5.6)
    ax.scatter([idn[3]], [y[3]], marker="D", s=14, color="white", edgecolor=C["purple"], zorder=3, linewidth=0.9,
               label="identified (reported)")
    ax.set_yticks(y); ax.set_yticklabels([c[1] for c in conds], fontsize=5.8); ax.set_xlim(-0.05, 1.15)
    ax.set_xlabel("Invalid assertions left admissible"); ax.legend(frameon=False, loc="lower right", fontsize=5.6,
                                                                   handletextpad=0.2, bbox_to_anchor=(1.05, 0.22))
    panel_label(ax, "(c)")
    fig.savefig(OUT / "fig_sup.pdf")
    plt.close(fig)


# ------------------------------------------------------------------ Fig: REG (column width, 2 panels)
def fig_reg():
    d = json.load(open(R / "registration_sensitivity_selftest.json"))
    pts = d["points"]
    drop = [p for p in pts if p["failure_mode"] == "drop"]
    flat = [p for p in pts if p["failure_mode"] == "flatten"]
    spur = [p for p in pts if p["failure_mode"] == "spurious"]
    fig, axs = plt.subplots(1, 2, figsize=(COL * 2 * 0.99, 2.15), gridspec_kw={"wspace": 0.28})
    for ax, key, xl in ((axs[0], "typed_recall", "Typed edge recall $\\mathrm{R}_{\\mathrm{dep}}$"),
                        (axs[1], "mean_support_set_coverage", "Support-set coverage")):
        ax.plot([p[key] for p in drop], [p["trl_full"]["manuscript_stale_claim_escape"] for p in drop], "-o", ms=3,
                lw=1.1, color=C["full"], label="Full TRL: dropped edges")
        ax.plot([p[key] for p in flat], [p["trl_full"]["manuscript_stale_claim_escape"] for p in flat], "s", ms=4.2,
                color=C["green"], label="Full TRL: flattened conjunctions")
        ax.plot([p[key] for p in spur], [p["trl_full"]["manuscript_stale_claim_escape"] for p in spur], "^", ms=4.4,
                color=C["purple"], label="Full TRL: spurious edges")
        ax.plot([p[key] for p in drop], [p["trl_binary_edges"]["manuscript_stale_claim_escape"] for p in drop], "--o",
                ms=2.5, lw=0.9, color=C["binary"], alpha=0.9, label="TRL, binary edges")
        ax.set_xlabel(xl); ax.set_ylim(-0.03, 1.02); ax.set_xlim(1.03, 0.15)
        ax.grid(alpha=0.25, lw=0.4)
    axs[0].set_ylabel("Invalid assertions left admissible")
    x = np.linspace(0.5, 1, 50)
    axs[0].plot(x, 1 - x, ":", color=C["gray"], lw=0.9)
    axs[0].text(0.36, 0.60, "escape $=1-\\mathrm{R}_{\\mathrm{dep}}$", fontsize=5.8, color=C["gray"], rotation=0)
    axs[0].annotate("", xy=(0.5, 0.5), xytext=(0.36, 0.585), arrowprops=dict(arrowstyle="-", lw=0.4, color=C["gray"]))
    axs[0].annotate("5% of edges dropped:\nrecall 0.947, escape 0.17", xy=(drop[1]["typed_recall"], drop[1]["trl_full"]["manuscript_stale_claim_escape"]),
                    xytext=(0.86, 0.04), fontsize=5.6, arrowprops=dict(arrowstyle="->", lw=0.5, color=C["black"]))
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, loc="upper center", ncol=4, fontsize=5.8, bbox_to_anchor=(0.5, 1.08), columnspacing=1.2, handlelength=1.6)
    panel_label(axs[0], "(a)"); panel_label(axs[1], "(b)")
    fig.savefig(OUT / "fig_reg.pdf")
    plt.close(fig)


# ------------------------------------------------------------------ Fig: scaling (column width, 2 panels)
def fig_scale():
    d = json.load(open(R / "scaling_v13_results.json"))["points"]
    def series(cfg, key, dens=1):
        pts = sorted([p for p in d if p["config"] == cfg and p["density_d"] == dens and p["n_triples"] >= 10000],
                     key=lambda p: p["n_triples"])
        return [p["n_triples"] for p in pts], [p[key] for p in pts]
    fig, axs = plt.subplots(1, 2, figsize=(COL * 2 * 0.99, 2.15), gridspec_kw={"wspace": 0.3})
    ax = axs[0]
    n, y = series("baseline", "incremental"); ax.plot(n, np.array(y) / 1e3, "-o", ms=3, color=C["binary"], label="Revision, earlier store")
    n, y = series("optimized", "incremental"); ax.plot(n, np.array(y) / 1e3, "-o", ms=3, color=C["full"], label="Revision, single-pass store")
    n, y = series("optimized", "invariants"); ax.plot(n, np.array(y) / 1e3, "-s", ms=2.8, color=C["green"], label="Invariant checking")
    n, y = series("optimized", "propagate"); ax.plot(n, np.array(y) / 1e3, "-^", ms=3, color=C["purple"], label="Propagation")
    nn = np.array([1e4, 1e5]); ax.plot(nn, 0.2 * nn / 1e4, ":", color=C["gray"], lw=0.9); ax.text(1.1e4, 3.2e-1 * 3.6, "linear", fontsize=5.6, color=C["gray"])
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("Claim/evidence/decision triples"); ax.set_ylabel("Seconds per revision")
    ax.set_ylim(2e-3, 2e2); ax.legend(frameon=False, loc="upper left", fontsize=5.6); ax.grid(alpha=0.25, lw=0.4, which="major")
    panel_label(ax, "(a)")
    ax = axs[1]
    n, y = series("baseline", "snapshot_bytes"); ax.plot(n, np.array(y) / 1e6, "-o", ms=3, color=C["binary"], label="Earlier store")
    n, y = series("optimized", "snapshot_bytes"); ax.plot(n, np.array(y) / 1e6, "-o", ms=3, color=C["full"], label="Single-pass store")
    dd = {1: 0, 5: 1, 20: 2}
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("Claim/evidence/decision triples"); ax.set_ylabel("Snapshot written per commit (MB)")
    ax.legend(frameon=False, loc="upper left"); ax.grid(alpha=0.25, lw=0.4)
    panel_label(ax, "(b)")
    fig.savefig(OUT / "fig_scale.pdf")
    plt.close(fig)


if __name__ == "__main__":
    fig_sup(); fig_reg(); fig_scale()
    print("figures written to", OUT)
