"""Unsupervised astrometric clustering and stability experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import HDBSCAN
from sklearn.preprocessing import RobustScaler

from gaia_pleiades.config import (
    FEATURE_COLUMNS,
    MIN_CLUSTER_SIZE,
    MIN_SAMPLES,
    SCALER_QUANTILE_RANGE,
    SENSITIVITY_CLUSTER_SIZES,
    STRENGTH_THRESHOLD,
    TARGET_ANCHOR,
    TARGET_ANCHOR_SCALES,
)


@dataclass
class ClusterResult:
    """Fitted objects plus row-aligned assignments."""

    scaler: RobustScaler
    model: HDBSCAN
    labels: np.ndarray
    strengths: np.ndarray
    target_label: int
    summaries: pd.DataFrame
    quantile_range: tuple[float, float]
    min_cluster_size: int


def cluster_summaries(frame: pd.DataFrame, labels: np.ndarray) -> pd.DataFrame:
    """Summarize every non-noise component in physical feature units."""
    labeled = frame.loc[:, FEATURE_COLUMNS].copy()
    labeled["cluster_label"] = labels
    labeled = labeled.loc[labeled["cluster_label"] >= 0]
    if labeled.empty:
        raise RuntimeError("HDBSCAN found no non-noise clusters")

    summaries = (
        labeled.groupby("cluster_label", sort=True)
        .agg(
            count=("parallax", "size"),
            parallax_median=("parallax", "median"),
            pmra_median=("pmra", "median"),
            pmdec_median=("pmdec", "median"),
        )
        .reset_index()
    )
    return summaries


def select_target_label(summaries: pd.DataFrame) -> int:
    """Select the component nearest a rough, external Pleiades anchor."""
    medians = summaries.loc[:, ["parallax_median", "pmra_median", "pmdec_median"]].to_numpy(
        dtype=float
    )
    anchor = np.asarray(TARGET_ANCHOR, dtype=float)
    scales = np.asarray(TARGET_ANCHOR_SCALES, dtype=float)
    distance = np.linalg.norm((medians - anchor) / scales, axis=1)
    return int(summaries.iloc[int(np.argmin(distance))]["cluster_label"])


def fit_clusters(
    frame: pd.DataFrame,
    *,
    min_cluster_size: int = MIN_CLUSTER_SIZE,
    quantile_range: tuple[float, float] = SCALER_QUANTILE_RANGE,
) -> ClusterResult:
    """Fit a deterministic HDBSCAN run on parallax and proper motion only."""
    features = frame.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(features).all():
        raise ValueError("Clustering features contain non-finite values")

    scaler = RobustScaler(quantile_range=quantile_range)
    scaled = scaler.fit_transform(features)
    model = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=MIN_SAMPLES,
        cluster_selection_method="eom",
        allow_single_cluster=False,
        copy=True,
    )
    labels = model.fit_predict(scaled)
    strengths = np.asarray(model.probabilities_, dtype=float)
    summaries = cluster_summaries(frame, labels)
    target_label = select_target_label(summaries)
    return ClusterResult(
        scaler=scaler,
        model=model,
        labels=labels,
        strengths=strengths,
        target_label=target_label,
        summaries=summaries,
        quantile_range=quantile_range,
        min_cluster_size=min_cluster_size,
    )


def add_assignments(frame: pd.DataFrame, result: ClusterResult) -> pd.DataFrame:
    """Attach labels and conservatively named HDBSCAN assignment strengths."""
    assigned = frame.copy()
    assigned["cluster_label"] = result.labels
    assigned["cluster_strength"] = result.strengths
    assigned["is_target_cluster"] = assigned["cluster_label"].eq(result.target_label)
    assigned["is_candidate"] = assigned["is_target_cluster"] & assigned["cluster_strength"].ge(
        STRENGTH_THRESHOLD
    )
    return assigned


def jaccard_index(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def run_sensitivity(frame: pd.DataFrame, baseline_candidate_ids: set[str]) -> pd.DataFrame:
    """Vary cluster size and robust-scaling quantiles around the main run."""
    experiments: list[tuple[str, int, tuple[float, float]]] = [
        ("cluster_size", size, SCALER_QUANTILE_RANGE) for size in SENSITIVITY_CLUSTER_SIZES
    ]
    experiments.append(("scaler_iqr", MIN_CLUSTER_SIZE, (25.0, 75.0)))

    rows: list[dict[str, Any]] = []
    for experiment, size, quantiles in experiments:
        result = fit_clusters(frame, min_cluster_size=size, quantile_range=quantiles)
        assigned = add_assignments(frame, result)
        target = assigned.loc[assigned["is_target_cluster"]]
        candidates = assigned.loc[assigned["is_candidate"]]
        candidate_ids = set(candidates["source_id"].astype(str))
        rows.append(
            {
                "experiment": experiment,
                "min_cluster_size": size,
                "quantile_low": quantiles[0],
                "quantile_high": quantiles[1],
                "target_cluster_count": int(len(target)),
                "candidate_count": int(len(candidates)),
                "jaccard_vs_main": jaccard_index(candidate_ids, baseline_candidate_ids),
                "parallax_median_mas": float(candidates["parallax"].median()),
                "pmra_median_mas_per_yr": float(candidates["pmra"].median()),
                "pmdec_median_mas_per_yr": float(candidates["pmdec"].median()),
            }
        )
    return pd.DataFrame(rows)


def model_bundle(result: ClusterResult) -> dict[str, Any]:
    """Return the fitted inference objects with enough metadata to interpret them."""
    return {
        "scaler": result.scaler,
        "hdbscan": result.model,
        "feature_columns": FEATURE_COLUMNS,
        "target_label": result.target_label,
        "strength_threshold": STRENGTH_THRESHOLD,
        "quantile_range": result.quantile_range,
        "min_cluster_size": result.min_cluster_size,
        "min_samples": MIN_SAMPLES,
        "target_anchor": TARGET_ANCHOR,
        "target_anchor_scales": TARGET_ANCHOR_SCALES,
        "warning": "cluster_strength is not a calibrated astrophysical membership probability",
    }
