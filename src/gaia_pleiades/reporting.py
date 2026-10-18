"""Tables, figures, and human-readable result artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from gaia_pleiades.config import STRENGTH_THRESHOLD, ProjectPaths

NAVY = "#071B33"
BLUE = "#1B6CA8"
CYAN = "#31C4D8"
GOLD = "#FFB703"
CORAL = "#FB6F6A"
MIST = "#DCE8F2"
GRAY = "#78909C"


def _configure_plotting() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "#F8FBFE",
            "axes.edgecolor": NAVY,
            "axes.labelcolor": NAVY,
            "axes.titlecolor": NAVY,
            "axes.titleweight": "bold",
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "grid.color": MIST,
            "grid.linewidth": 0.8,
            "xtick.color": NAVY,
            "ytick.color": NAVY,
        }
    )


def _save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(
        path,
        dpi=180,
        bbox_inches="tight",
        facecolor="white",
        metadata={"Software": "gaia-pleiades-member-finder"},
    )
    plt.close(fig)


def plot_sky(field: pd.DataFrame, candidates: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(field["ra"], field["dec"], s=4, c=GRAY, alpha=0.12, linewidths=0)
    points = ax.scatter(
        candidates["ra"],
        candidates["dec"],
        s=13,
        c=candidates["cluster_strength"],
        cmap="plasma",
        vmin=STRENGTH_THRESHOLD,
        vmax=1,
        alpha=0.9,
        linewidths=0,
    )
    colorbar = fig.colorbar(points, ax=ax, pad=0.02)
    colorbar.set_label("HDBSCAN assignment strength")
    ax.invert_xaxis()
    ax.set(title="Pleiades kinematic candidates on the sky", xlabel="RA (deg)", ylabel="Dec (deg)")
    ax.grid(alpha=0.55)
    fig.text(
        0.5,
        0.01,
        "Five-degree Gaia DR3 field; right ascension increases to the left.",
        ha="center",
        color=GRAY,
        fontsize=9,
    )
    _save(fig, path)


def plot_proper_motion(
    field: pd.DataFrame, candidates: pd.DataFrame, reference_cluster: pd.DataFrame, path: Path
) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(field["pmra"], field["pmdec"], s=4, c=GRAY, alpha=0.1, linewidths=0)
    points = ax.scatter(
        candidates["pmra"],
        candidates["pmdec"],
        s=15,
        c=candidates["cluster_strength"],
        cmap="plasma",
        vmin=STRENGTH_THRESHOLD,
        vmax=1,
        alpha=0.9,
        linewidths=0,
        label="This analysis",
    )
    cluster = reference_cluster.iloc[0]
    ax.scatter(
        [cluster["pmRA"]],
        [cluster["pmDE"]],
        marker="*",
        s=220,
        c=CYAN,
        edgecolor=NAVY,
        linewidth=0.8,
        label="Hunt & Reffert 2024 centroid",
        zorder=5,
    )
    fig.colorbar(points, ax=ax, pad=0.02).set_label("HDBSCAN assignment strength")
    ax.set(
        title="The density-selected component is kinematically compact",
        xlabel=r"Proper motion $\mu_{\alpha*}$ (mas yr$^{-1}$)",
        ylabel=r"Proper motion $\mu_{\delta}$ (mas yr$^{-1}$)",
    )
    ax.grid(alpha=0.55)
    ax.legend(frameon=True, loc="upper right")
    _save(fig, path)


def plot_parallax(
    field: pd.DataFrame, candidates: pd.DataFrame, reference_cluster: pd.DataFrame, path: Path
) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    bins = np.linspace(2, 15, 80)
    ax.hist(field["parallax"], bins=bins, color=GRAY, alpha=0.28, label="Quality-filtered field")
    ax.hist(candidates["parallax"], bins=bins, color=GOLD, alpha=0.85, label="Candidates")
    reference_parallax = float(reference_cluster.iloc[0]["Plx"])
    ax.axvline(reference_parallax, color=CYAN, lw=2, label="Hunt & Reffert 2024")
    ax.axvline(
        1000 / 136.2,
        color=CORAL,
        lw=2,
        ls="--",
        label="Melis et al. 2014 distance equivalent",
    )
    ax.set(
        title="Candidate parallaxes agree with external Pleiades measurements",
        xlabel="Gaia DR3 parallax (mas)",
        ylabel="Sources per bin",
        xlim=(5.5, 9.5),
    )
    ax.grid(axis="y", alpha=0.55)
    ax.legend(frameon=True)
    _save(fig, path)


def plot_cmd(field: pd.DataFrame, candidates: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 7))
    ax.scatter(field["bp_rp"], field["absolute_g_naive"], s=4, c=GRAY, alpha=0.08, linewidths=0)
    points = ax.scatter(
        candidates["bp_rp"],
        candidates["absolute_g_naive"],
        s=14,
        c=candidates["cluster_strength"],
        cmap="plasma",
        vmin=STRENGTH_THRESHOLD,
        vmax=1,
        alpha=0.9,
        linewidths=0,
    )
    fig.colorbar(points, ax=ax, pad=0.02).set_label("HDBSCAN assignment strength")
    ax.invert_yaxis()
    ax.set(
        title="Gaia Color–Magnitude Diagram: Pleiades Kinematic Candidates",
        xlabel=r"Gaia $G_{BP}-G_{RP}$ (mag)",
        ylabel=r"Naive absolute $G$ (mag)",
        xlim=(-0.5, 4.8),
    )
    ax.grid(alpha=0.45)
    fig.text(
        0.5,
        0.01,
        "Color and magnitude were not clustering inputs; extinction and parallax "
        "zero point are uncorrected.",
        ha="center",
        color=GRAY,
        fontsize=8.5,
    )
    _save(fig, path)


def plot_strength(field: pd.DataFrame, path: Path) -> None:
    target = field.loc[field["is_target_cluster"], "cluster_strength"]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.hist(target, bins=np.linspace(0, 1, 41), color=BLUE, alpha=0.88)
    ax.axvline(
        STRENGTH_THRESHOLD,
        color=CORAL,
        lw=2.2,
        ls="--",
        label=f"Candidate threshold = {STRENGTH_THRESHOLD:.1f}",
    )
    ax.set(
        title="Conservative assignment-strength threshold",
        xlabel="HDBSCAN assignment strength (not a calibrated probability)",
        ylabel="Target-component sources",
        xlim=(0, 1),
    )
    ax.grid(axis="y", alpha=0.55)
    ax.legend(frameon=True)
    _save(fig, path)


def plot_sensitivity(sensitivity: pd.DataFrame, path: Path) -> None:
    cluster_size = sensitivity.loc[sensitivity["experiment"].eq("cluster_size")]
    iqr = sensitivity.loc[sensitivity["experiment"].eq("scaler_iqr")].iloc[0]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(
        cluster_size["min_cluster_size"],
        cluster_size["candidate_count"],
        marker="o",
        ms=7,
        lw=2.2,
        color=BLUE,
        label="10th–90th percentile scaling",
    )
    ax.scatter(
        [iqr["min_cluster_size"]],
        [iqr["candidate_count"]],
        marker="D",
        s=75,
        color=CORAL,
        label="Standard IQR scaling check",
        zorder=5,
    )
    for _, row in cluster_size.iterrows():
        ax.annotate(
            f"J={row['jaccard_vs_main']:.3f}",
            (row["min_cluster_size"], row["candidate_count"]),
            xytext=(0, 9),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=NAVY,
        )
    ax.annotate(
        f"IQR J={iqr['jaccard_vs_main']:.3f}",
        (iqr["min_cluster_size"], iqr["candidate_count"]),
        xytext=(10, 0),
        textcoords="offset points",
        ha="left",
        va="center",
        fontsize=8,
        color=NAVY,
    )
    ax.set(
        title="Candidate selection is stable across HDBSCAN settings",
        xlabel="Minimum cluster size",
        ylabel="Candidate count",
        ylim=(855.5, 868.5),
    )
    ax.grid(alpha=0.55)
    ax.legend(frameon=True)
    _save(fig, path)


def plot_catalog_agreement(agreement: dict[str, Any], path: Path) -> None:
    labels = ["Candidate\nagreement", "Eligible catalog\nrecovery", "All-catalog\nrecovery"]
    values = [
        agreement["candidate_catalog_agreement"],
        agreement["eligible_reference_recovery"],
        agreement["all_catalog_recovery"],
    ]
    fig, ax = plt.subplots(figsize=(8, 5.5))
    bars = ax.bar(labels, np.asarray(values) * 100, color=[BLUE, CYAN, GOLD], width=0.62)
    for bar, value in zip(bars, values, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.5,
            f"{value:.1%}",
            ha="center",
            va="bottom",
            color=NAVY,
            fontweight="bold",
        )
    ax.set(
        title="Agreement with the current Hunt–Reffert catalog",
        ylabel="Fraction (%)",
        ylim=(0, 105),
    )
    ax.grid(axis="y", alpha=0.55)
    fig.text(
        0.5,
        0.01,
        "Related-method benchmark, not independent ground-truth accuracy.",
        ha="center",
        color=GRAY,
        fontsize=9,
    )
    _save(fig, path)


def write_metrics(metrics: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_results(metrics: dict[str, Any], path: Path) -> None:
    stats = metrics["candidate_statistics"]
    agreement = metrics["reference_agreement"]
    stability = metrics["stability"]
    comparison_rows = "\n".join(
        [
            "| Median parallax | "
            f"{stats['parallax_median_mas']:.4f} mas | "
            f"{stats['reference_parallax_mas']:.4f} mas (Hunt & Reffert 2024) |",
            "| Median pmRA* | "
            f"{stats['pmra_median_mas_per_yr']:.4f} mas/yr | "
            f"{stats['reference_pmra_mas_per_yr']:.4f} mas/yr |",
            "| Median pmDec | "
            f"{stats['pmdec_median_mas_per_yr']:.4f} mas/yr | "
            f"{stats['reference_pmdec_mas_per_yr']:.4f} mas/yr |",
            "| Descriptive inverse-parallax distance | "
            f"{stats['inverse_parallax_distance_median_pc']:.2f} pc | "
            f"{stats['vlbi_distance_pc']:.1f} ± "
            f"{stats['vlbi_distance_error_pc']:.1f} pc (VLBI) |",
        ]
    )
    text = f"""# Results

## Headline result

The pipeline selected **{stats["count"]:,} Pleiades kinematic candidate members** from
{metrics["sample"]["quality_filtered_sources"]:,} quality-filtered Gaia DR3 sources in a
five-degree field. The model used only parallax and two-component proper motion.

| Measurement | This analysis | External comparison |
|---|---:|---:|
{comparison_rows}

## Catalog agreement

- {agreement["overlap_count"]:,} of {agreement["candidate_count"]:,} candidates occur in the
  current high-confidence, within-tidal-radius Hunt–Reffert list
  (**{agreement["candidate_catalog_agreement"]:.2%} candidate agreement**).
- The pipeline recovers {agreement["overlap_count"]:,} of
  {agreement["reference_members_eligible_in_query"]:,} comparable catalog sources that pass
  this project's query (**{agreement["eligible_reference_recovery"]:.2%} conditional recovery**).
- Against all {agreement["reference_catalog_members"]:,} high-confidence catalog sources,
  including objects excluded by this query, recovery is
  **{agreement["all_catalog_recovery"]:.2%}**.

These are catalog-agreement measurements, not accuracy against ground truth. Both studies use
Gaia DR3 astrometry and density-based clustering.

## Stability

Across the tested `min_cluster_size` values, candidate counts range from
{stability["candidate_count_min"]:,} to {stability["candidate_count_max"]:,}; Jaccard overlap
with the main result ranges from {stability["jaccard_min"]:.3f} to
{stability["jaccard_max"]:.3f}. Switching to standard IQR scaling gives a Jaccard overlap of
{stability["iqr_scaler_jaccard"]:.3f}.

## Important limits

- These are kinematic candidates, not confirmed or necessarily gravitationally bound members.
- `cluster_strength` is HDBSCAN assignment strength, not a calibrated membership probability.
- The quality cuts reduce contamination but bias the sample against faint sources and binaries.
- The five-degree cone approximates the tidal region and does not cover the full stellar tails.
- Gaia's position-, color-, and magnitude-dependent parallax zero point was not corrected.
- The inverse-parallax distance is a descriptive summary, not a Bayesian distance estimate.
- Photometry and the comparison catalog were withheld from clustering and used afterward only.

## Figures

![Proper-motion selection](figures/proper_motion.png)

![Color–magnitude corroboration](figures/color_magnitude_diagram.png)

![Parameter sensitivity](figures/sensitivity.png)
"""
    path.write_text(text, encoding="utf-8")


def generate_report_artifacts(
    paths: ProjectPaths,
    field: pd.DataFrame,
    candidates: pd.DataFrame,
    reference_cluster: pd.DataFrame,
    sensitivity: pd.DataFrame,
    metrics: dict[str, Any],
) -> None:
    _configure_plotting()
    plot_sky(field, candidates, paths.figures / "sky_distribution.png")
    plot_proper_motion(field, candidates, reference_cluster, paths.figures / "proper_motion.png")
    plot_parallax(field, candidates, reference_cluster, paths.figures / "parallax.png")
    plot_cmd(field, candidates, paths.figures / "color_magnitude_diagram.png")
    plot_strength(field, paths.figures / "assignment_strength.png")
    plot_sensitivity(sensitivity, paths.figures / "sensitivity.png")
    plot_catalog_agreement(metrics["reference_agreement"], paths.figures / "agreement.png")
    write_metrics(metrics, paths.metrics)
    write_results(metrics, paths.results)
