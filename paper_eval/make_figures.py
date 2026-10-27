"""
Draws the data figures of the paper (paper/figures/fig_*.pdf) from the JSON
files in results/. The TikZ diagrams (architecture, SSA example, layout,
modules, flow) are separate LaTeX sources.

Series colors follow one fixed categorical order, and every bar series also
has its own hatch, so the figures stay readable in grayscale print and for
color-vision deficiencies. Every plotted number is also in a table.

    python3 paper_eval/make_figures.py
"""

import os
import statistics

import matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt  # noqa: E402

from common import read, PAPER, reduction  # noqa: E402

FIG = os.path.join(PAPER, "figures")
COL = 3.45   # IEEE column width in inches
WIDE = 7.1   # text width
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
HATCH = ["", "////", "\\\\\\\\", "....", "xxxx", "----"]
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#d9d8d4"
RAW_GRAY = "#a8a7a2"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 7.5, "axes.labelsize": 7.5, "axes.titlesize": 7.5, "legend.fontsize": 6.8,
    "xtick.labelsize": 6.8, "ytick.labelsize": 6.8, "axes.edgecolor": MUTED,
    "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6,
    "hatch.linewidth": 0.5, "hatch.color": "white", "legend.frameon": False,
    "pdf.fonttype": 42,
})


def grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("wrote", name)


def grouped_bars(ax, labels, series, names, width=0.8, log=False):
    n = len(series)
    w = width / n
    for k, (values, name) in enumerate(zip(series, names)):
        xs = [i - width / 2 + w * (k + 0.5) for i in range(len(labels))]
        ax.bar(xs, values, w * 0.92, color=SERIES[k], hatch=HATCH[k], label=name,
               edgecolor="white", linewidth=0)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    if log:
        ax.set_yscale("log")
    grid(ax)


def fig_reduction(m):
    labels = [r["id"] for r in m]
    fig, ax = plt.subplots(figsize=(WIDE, 1.9))
    grouped_bars(ax, labels, [[r["tac_instructions"] for r in m],
                              [r["opt_instructions_base_passes"] for r in m],
                              [r["opt_instructions"] for r in m]],
                 ["Raw TAC", "Optimized, five base passes", "Optimized, all seven passes"])
    for i, r in enumerate(m):
        ax.annotate(f'{r["instruction_reduction"]:.0f}%', (i, r["tac_instructions"]),
                    xytext=(0, 2), textcoords="offset points", ha="center", fontsize=5.8, color=MUTED)
    ax.axvline(6.5, color=GRID, linewidth=0.8)
    ax.set_ylabel("Instructions")
    ax.set_ylim(0, max(r["tac_instructions"] for r in m) * 1.12)
    ax.legend(ncol=3, bbox_to_anchor=(0, 1.02), loc="lower left", borderaxespad=0)
    save(fig, "fig_reduction.pdf")


def fig_ablation(a):
    order = [("none", "No pass (SSA form)"), ("no_dce", "All but DCE"),
             ("no_copy_prop", "All but copy propagation"), ("base", "Five base passes"),
             ("base+sccp", "Base + SCCP"), ("base+copy_prop", "Base + copy propagation"),
             ("no_cfg", "All but CFG simplification"), ("no_fold", "All but folding"),
             ("no_trivial_phi", "All but trivial-$\\phi$ removal"), ("no_sccp", "All but SCCP"),
             ("no_gvn", "All but value numbering")]
    fig, axes = plt.subplots(1, 2, figsize=(COL, 2.5), sharey=True)
    for ax, (key, title) in zip(axes, (("no_input", "Without input"), ("with_input", "With input"))):
        x = a[key]
        base = x["instructions"]["all"]
        vals = [100 * (x["instructions"][k] - base) / base for k, _ in order]
        raw = 100 * (x["raw_instructions"] - base) / base
        ys = list(range(len(order)))[::-1]
        ax.barh(ys, vals, 0.7, color=SERIES[0], edgecolor="white", linewidth=0)
        ax.barh(len(order), raw, 0.7, color=RAW_GRAY, edgecolor="white", linewidth=0)
        for y, v in zip(ys, vals):
            ax.annotate(f"{v:+.1f}", (v, y), xytext=(2, 0), textcoords="offset points",
                        va="center", fontsize=5.6, color=MUTED)
        ax.annotate(f"{raw:+.1f}", (raw, len(order)), xytext=(2, 0), textcoords="offset points",
                    va="center", fontsize=5.6, color=MUTED)
        ax.set_title(title, color=INK)
        ax.set_xlim(0, max(vals + [raw]) * 1.28)
        grid(ax, "x")
    axes[0].set_yticks(list(range(len(order) + 1)))
    axes[0].set_yticklabels([lbl for _, lbl in order][::-1] + ["Raw TAC (unoptimized)"])
    fig.subplots_adjust(wspace=0.18, bottom=0.16)
    fig.supxlabel("Instructions relative to all seven passes (%)", fontsize=7, y=0.0)
    save(fig, "fig_ablation.pdf")


def fig_sizes(m):
    labels = [r["id"] for r in m]
    fig, ax = plt.subplots(figsize=(WIDE, 2.0))
    grouped_bars(ax, labels, [[r["raw_text_bytes"] for r in m], [r["opt_text_bytes"] for r in m],
                              [r["clir_bytes"] for r in m], [r["huffman_bytes"] for r in m],
                              [r["freq_huffman_bytes"] for r in m], [r["columnar_bytes"] for r in m]],
                 ["Raw TAC text", "Optimized text", "CLIR", "CLIR + canonical Huffman",
                  "CLIR + frequency-table Huffman", "Columnar"], log=True)
    ax.axvline(6.5, color=GRID, linewidth=0.8)
    ax.set_ylabel("Bytes (log scale)")
    ax.legend(ncol=6, bbox_to_anchor=(0, 1.02), loc="lower left", borderaxespad=0)
    ax.set_ylim(10, 2000)
    save(fig, "fig_benchmark_sizes.pdf")


def fig_compare(cmp):
    b = cmp["benchmarks"]
    labels = [r["id"] for r in b]
    s = [r["summary"]["opt_text"] for r in b]
    fig, ax = plt.subplots(figsize=(WIDE, 1.9))
    grouped_bars(ax, labels, [[r["opt_text"]["input"] for r in b], [x["best_framed"] for x in s],
                              [x["best_headerless"] for x in s], [x["best_dictionary"] for x in s],
                              [r["clir"]["input"] for r in b]],
                 ["Optimized text", "Best of Brotli/Zstd/xz", "Best, headerless",
                  "Best with shared dictionary", "CLIR"], log=True)
    ax.axvline(6.5, color=GRID, linewidth=0.8)
    ax.set_ylabel("Bytes (log scale)")
    ax.legend(ncol=5, bbox_to_anchor=(0, 1.02), loc="lower left", borderaxespad=0)
    ax.set_ylim(5, 1500)
    save(fig, "fig_compare.pdf")


def fig_density(m):
    labels = [r["id"] for r in m]
    fig, ax = plt.subplots(figsize=(COL, 1.8))
    d = [r["density"] for r in m]
    grouped_bars(ax, labels, [[x["raw_text_bits_per_raw_instr"] for x in d],
                              [x["clir_body_bits_per_opt_instr"] for x in d],
                              [x["clir_bits_per_raw_instr"] for x in d]],
                 ["Raw text per raw instr.", "CLIR body per opt. instr.", "CLIR package per raw instr."])
    ax.set_ylabel("Bits per instruction")
    ax.tick_params(axis="x", labelsize=5.5, rotation=90)
    ax.legend(ncol=1, fontsize=6, bbox_to_anchor=(0, 1.02), loc="lower left", borderaxespad=0)
    save(fig, "fig_density.pdf")


def fig_scaling(s, cmp):
    classes = s["size_classes"]
    progs = s["programs"]
    med = lambda rows, key: statistics.median(r[key] for r in rows)
    xs, series = [], {k: [] for k in ("clir_bytes", "huffman_bytes", "freq_huffman_bytes",
                                       "deflate_clir", "brotli_clir", "columnar_bytes")}
    for n in classes:
        rows = [p for p in progs if p["statements"] == n]
        xs.append(med(rows, "raw_instructions"))
        for k in series:
            series[k].append(med(rows, k))
    names = {"clir_bytes": "CLIR", "huffman_bytes": "+ canonical Huffman",
             "freq_huffman_bytes": "+ frequency-table Huffman", "deflate_clir": "+ DEFLATE",
             "brotli_clir": "+ Brotli", "columnar_bytes": "Columnar"}
    markers = ["o", "s", "^", "D", "v", "P"]
    fig, ax = plt.subplots(figsize=(COL, 2.3))
    for k, (key, ys) in enumerate(series.items()):
        ax.plot(xs, ys, color=SERIES[k], marker=markers[k], markersize=3.2, linewidth=1.0, label=names[key])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Median raw instructions per size class")
    ax.set_ylabel("Median encoded size (bytes)")
    grid(ax, "both")
    ax.legend(loc="upper left", fontsize=6)
    save(fig, "fig_scaling.pdf")


def fig_throughput(s):
    progs = s["programs"]
    fig, ax = plt.subplots(figsize=(COL, 1.9))
    ax.scatter([p["raw_instructions"] for p in progs], [p["time_ms"] for p in progs], s=9,
               color=SERIES[0], edgecolors="white", linewidths=0.4)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Raw instructions")
    ax.set_ylabel("Compilation time (ms)")
    grid(ax, "both")
    save(fig, "fig_throughput.pdf")


def main():
    os.makedirs(FIG, exist_ok=True)
    m = read("measure.json")["benchmarks"]
    fig_reduction(m)
    fig_ablation(read("ablation.json"))
    fig_sizes(m)
    fig_compare(read("compare.json"))
    fig_density(m)
    fig_scaling(read("scaling.json"), read("compare.json"))
    fig_throughput(read("scaling.json"))


if __name__ == "__main__":
    main()
