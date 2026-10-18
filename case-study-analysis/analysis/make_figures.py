"""Render scientific teaching figures from verified observed-data outputs."""

from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "analysis/.mpl-cache"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd

INK = "#162c36"
TEAL = "#006c72"
OCHRE = "#a96500"
GRAY = "#7e8c90"
PALE = "#e9efef"
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 12,
        "axes.labelcolor": INK,
        "text.color": INK,
        "axes.edgecolor": "#b2bfc2",
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.fonttype": "none",
        "svg.hashsalt": "pleiades-revival-2026",
    }
)
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)
REPRO = ROOT / "analysis/reproduction"
f = pd.read_csv(
    REPRO / "data/processed/pleiades_field_clustered.csv", dtype={"source_id": "string"}
)
c = f.loc[f.is_candidate]
assert len(f) == 12520 and len(c) == 866 and int(f.is_target_cluster.sum()) == 1288, (
    "Review teaching annotations for changed data."
)


def save(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(
            OUT / f"{name}.{ext}",
            dpi=180,
            bbox_inches="tight",
            facecolor="white",
            metadata={"Creator": "Gaia Pleiades continuation"}
            if ext == "svg"
            else {"Software": "Gaia Pleiades continuation"},
        )
    plt.close(fig)


def header(fig, eyebrow, title, subtitle):
    fig.text(0.06, 0.96, eyebrow.upper(), size=10, weight="bold", color=TEAL)
    fig.text(0.06, 0.905, title, size=25, fontfamily="DejaVu Serif", weight="bold")
    fig.text(0.06, 0.86, subtitle, size=12, color=INK)


def credit(fig):
    fig.text(
        0.06,
        0.025,
        "Archived Gaia DR3 • ESA/Gaia/DPAC • Analysis: Alison Thomas, with AI assistance",
        size=9,
        color=INK,
    )


fig, axes = plt.subplots(1, 2, figsize=(13, 7.4))
fig.subplots_adjust(left=0.075, right=0.96, bottom=0.23, top=0.75, wspace=0.25)
header(
    fig,
    "Gaia Pleiades · observation and selection",
    "A shared motion. A stellar sequence.",
    "866 kinematic candidates selected from 12,520 quality-filtered stars in a 5° field.",
)
ax = axes[0]
ax.scatter(
    f.pmra,
    f.pmdec,
    s=6,
    c=GRAY,
    alpha=0.18,
    rasterized=True,
    linewidths=0,
    label="Filtered field",
)
ax.scatter(
    c.pmra,
    c.pmdec,
    s=12,
    c=TEAL,
    alpha=0.75,
    rasterized=True,
    linewidths=0,
    label="866 candidates",
)
ax.set(
    xlabel="Proper motion in RA* (mas/year)",
    ylabel="Proper motion in Dec (mas/year)",
    xlim=(-20, 50),
    ylim=(-80, -10),
)
ax.set_title(
    "01 / Inputs to the density fit", loc="left", size=14, pad=13, weight="bold"
)
ax.legend(frameon=False, loc="lower right", markerscale=2, fontsize=10)
ax = axes[1]
ax.scatter(
    f.bp_rp, f.absolute_g_naive, s=6, c=GRAY, alpha=0.13, rasterized=True, linewidths=0
)
ax.scatter(
    c.bp_rp, c.absolute_g_naive, s=13, c=TEAL, alpha=0.72, rasterized=True, linewidths=0
)
ax.set(
    xlabel="Gaia BP − RP color (mag)",
    ylabel="Naive absolute G magnitude",
    xlim=(-0.4, 4.5),
    ylim=(15, -3),
)
ax.set_title("02 / A check after selection", loc="left", size=14, pad=13, weight="bold")
for ax in axes:
    ax.grid(alpha=0.2)
    ax.set_axisbelow(True)
fig.text(
    0.075,
    0.09,
    "RA* includes cos(Dec). Parallax is the third clustering input.",
    size=9,
)
fig.text(
    0.565,
    0.09,
    "Color and magnitude are held out of the fit; absolute G reuses parallax.\nPhotometric quality cuts apply; extinction and zero point are uncorrected.",
    size=9,
)
credit(fig)
save(fig, "motion-and-sequence")

fig = plt.figure(figsize=(13, 7.5))
ax = fig.add_axes([0.04, 0.1, 0.92, 0.69])
ax.set(xlim=(0, 100), ylim=(0, 65))
ax.axis("off")
header(
    fig,
    "How a star becomes a candidate",
    "A selection rule you can trace.",
    "Unsupervised clustering finds density groups; a rough external anchor names the target group.",
)
boxes = [
    (
        2,
        35,
        28,
        23,
        "01  THE SAMPLE",
        "12,520 Gaia DR3 sources",
        "5° field + quality cuts\nParallax and two proper motions",
    ),
    (
        36,
        35,
        28,
        23,
        "02  THE DENSITY FIT",
        "1,288 in target component",
        "Robust scaling → HDBSCAN\nExternal Pleiades anchor",
    ),
    (
        70,
        35,
        28,
        23,
        "03  THE RULE",
        "866 kinematic candidates",
        "Target component AND\nassignment strength ≥ 0.5",
    ),
]
for x, y, w, h, label, title, body in boxes:
    ax.add_patch(Rectangle((x, y), w, h, facecolor=PALE, edgecolor="none"))
    ax.text(x + 2, y + h - 5, label, size=10, weight="bold", color=TEAL)
    ax.text(x + 2, y + h - 11, title, size=13, weight="bold")
    ax.text(x + 2, y + h - 17, body, size=10, linespacing=1.7, va="top")
for x in (31, 65):
    ax.annotate(
        "",
        xy=(x + 4, 46),
        xytext=(x, 46),
        arrowprops={"arrowstyle": "->", "color": TEAL, "lw": 2},
    )
ax.text(
    2,
    25,
    "Then ask: does other evidence tell a consistent story?",
    size=16,
    fontfamily="DejaVu Serif",
    weight="bold",
)
ax.text(
    2,
    16,
    "Held-out Gaia features\nColor–magnitude sequence\nAvailable radial velocities",
    size=11,
    linespacing=1.6,
)
ax.text(
    37,
    16,
    "Published comparison\n781 shared source IDs\nRelated data and methods",
    size=11,
    linespacing=1.6,
)
ax.text(
    72,
    16,
    "Selection sensitivity\nThresholds, scaling, neighbors\nFeature ablation and baseline",
    size=11,
    linespacing=1.6,
)
fig.text(
    0.06,
    0.072,
    "Assignment strength describes this density fit. It is not a probability of physical membership.",
    size=12,
    color=OCHRE,
    weight="bold",
)
credit(fig)
save(fig, "candidate-path")

fig = plt.figure(figsize=(12, 7))
ax = fig.add_axes([0.075, 0.22, 0.86, 0.49])
ax.axis("off")
header(
    fig,
    "A comparison with explicit denominators",
    "Overlap is evidence. It is not accuracy.",
    "Hunt & Reffert (2024): catalog score ≥ 0.5, within the estimated King tidal radius.",
)
rows = [
    ("This selection", 781, 85, 866, "781 shared / 866 candidates = 90.2%"),
    (
        "Reference, in snapshot",
        781,
        91,
        872,
        "781 shared / 872 eligible reference = 89.6%",
    ),
    ("Reference, full subset", 781, 233, 1014, "781 shared / 1,014 reference = 77.0%"),
]
ax.set(xlim=(0, 1050), ylim=(-0.7, 3.4))
for i, (label, shared, other, total, ratio) in enumerate(rows):
    y = 2.7 - i * 1.15
    ax.barh(y, shared, height=0.36, color=TEAL)
    ax.barh(y, other, left=shared, height=0.36, color=OCHRE if i == 0 else GRAY)
    ax.text(0, y + 0.34, label, size=12, weight="bold")
    ax.text(16, y, "781 shared", size=11, color="white", va="center")
    ax.text(total + 8, y, str(total), size=11, va="center")
    ax.text(0, y - 0.4, ratio, size=11)
fig.text(
    0.075,
    0.135,
    "85 candidate-only and 91 eligible-reference-only sources are disagreements, not known errors.\n142 reference sources are absent from the filtered input and cannot be recovered by this run.",
    size=11,
    linespacing=1.5,
)
credit(fig)
save(fig, "catalog-overlap")
table = pd.read_csv(ROOT / "data/checks/threshold_sensitivity.csv")
fig, ax = plt.subplots(figsize=(11, 6.8))
fig.subplots_adjust(left=0.12, right=0.94, bottom=0.23, top=0.73)
header(
    fig,
    "Sensitivity · one choice at a time",
    "The threshold changes the answer.",
    "The same target component contains 1,288 sources before the assignment-strength cut.",
)
ax.plot(
    table.strength_threshold, table.candidate_count, marker="o", ms=8, color=TEAL, lw=2
)
ax.scatter([0.5], [866], s=160, color=OCHRE, zorder=4)
for x, y in zip(table.strength_threshold, table.candidate_count):
    ax.annotate(
        f"{y:,}",
        (x, y),
        xytext=(0, 12),
        textcoords="offset points",
        ha="center",
        weight="bold",
    )
ax.set(
    xlabel="Minimum HDBSCAN assignment strength",
    ylabel="Selected candidates",
    xticks=[0.3, 0.5, 0.7, 0.9],
    ylim=(0, 1250),
    xlim=(0.25, 0.95),
)
ax.grid(alpha=0.2)
ax.set_axisbelow(True)
fig.text(
    0.12,
    0.12,
    "Original threshold: 0.5 → 866 candidates. These are alternative selections, not confidence intervals.",
    size=10,
)
fig.text(
    0.12,
    0.085,
    "No threshold was selected by maximizing comparison-catalog agreement.",
    size=10,
    color=OCHRE,
)
credit(fig)
save(fig, "threshold-sensitivity")
print("Rendered four teaching figures, each PNG and SVG.")
