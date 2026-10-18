"""Post-clustering catalog agreement and independent physical checks."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from gaia_pleiades.config import (
    LITERATURE_RV_ERROR_KMS,
    LITERATURE_RV_KMS,
    REFERENCE_PROBABILITY_THRESHOLD,
    VLBI_DISTANCE_ERROR_PC,
    VLBI_DISTANCE_PC,
)


def robust_sigma(values: pd.Series) -> float:
    """Return 1.4826 times the median absolute deviation."""
    array = values.dropna().to_numpy(dtype=float)
    if not len(array):
        return float("nan")
    median = np.median(array)
    return float(1.4826 * np.median(np.abs(array - median)))


def reference_agreement(
    field: pd.DataFrame, candidates: pd.DataFrame, members: pd.DataFrame
) -> dict[str, Any]:
    """Compare candidates with a related catalog without treating it as truth."""
    reference = members.loc[
        members["catalog_probability"].ge(REFERENCE_PROBABILITY_THRESHOLD) & members["inrt"].eq(1)
    ]
    field_ids = set(field["source_id"].astype(str))
    candidate_ids = set(candidates["source_id"].astype(str))
    reference_ids = set(reference["source_id"].astype(str))
    eligible_reference_ids = reference_ids & field_ids
    overlap_ids = candidate_ids & reference_ids

    candidate_count = len(candidate_ids)
    eligible_count = len(eligible_reference_ids)
    reference_count = len(reference_ids)
    overlap_count = len(overlap_ids)
    return {
        "reference_catalog_members": reference_count,
        "reference_members_eligible_in_query": eligible_count,
        "candidate_count": candidate_count,
        "overlap_count": overlap_count,
        "candidate_catalog_agreement": overlap_count / candidate_count,
        "eligible_reference_recovery": overlap_count / eligible_count,
        "all_catalog_recovery": overlap_count / reference_count,
        "candidate_only_count": candidate_count - overlap_count,
        "eligible_reference_only_count": eligible_count - overlap_count,
        "interpretation": (
            "Agreement benchmark, not ground-truth accuracy; both analyses use Gaia DR3 "
            "and density-based clustering."
        ),
    }


def candidate_statistics(
    candidates: pd.DataFrame, reference_cluster: pd.DataFrame
) -> dict[str, Any]:
    """Summarize the candidate population and comparison values."""
    if candidates.empty:
        raise RuntimeError("No Pleiades candidates were selected")
    cluster = reference_cluster.iloc[0]
    radial_velocity = candidates.loc[
        candidates["radial_velocity"].notna()
        & candidates["radial_velocity_error"].notna()
        & candidates["radial_velocity_error"].lt(5.0),
        "radial_velocity",
    ]

    parallax_median = float(candidates["parallax"].median())
    distance_median = float(candidates["distance_pc_inverse_parallax"].median())
    pmra_median = float(candidates["pmra"].median())
    pmdec_median = float(candidates["pmdec"].median())
    rv_median = float(radial_velocity.median()) if len(radial_velocity) else float("nan")
    return {
        "count": int(len(candidates)),
        "cluster_strength_median": float(candidates["cluster_strength"].median()),
        "parallax_median_mas": parallax_median,
        "parallax_robust_sigma_mas": robust_sigma(candidates["parallax"]),
        "pmra_median_mas_per_yr": pmra_median,
        "pmra_robust_sigma_mas_per_yr": robust_sigma(candidates["pmra"]),
        "pmdec_median_mas_per_yr": pmdec_median,
        "pmdec_robust_sigma_mas_per_yr": robust_sigma(candidates["pmdec"]),
        "inverse_parallax_distance_median_pc": distance_median,
        "vlbi_distance_pc": VLBI_DISTANCE_PC,
        "vlbi_distance_error_pc": VLBI_DISTANCE_ERROR_PC,
        "distance_difference_pc": distance_median - VLBI_DISTANCE_PC,
        "reference_parallax_mas": float(cluster["Plx"]),
        "reference_pmra_mas_per_yr": float(cluster["pmRA"]),
        "reference_pmdec_mas_per_yr": float(cluster["pmDE"]),
        "parallax_difference_from_reference_mas": parallax_median - float(cluster["Plx"]),
        "pmra_difference_from_reference_mas_per_yr": pmra_median - float(cluster["pmRA"]),
        "pmdec_difference_from_reference_mas_per_yr": pmdec_median - float(cluster["pmDE"]),
        "radial_velocity_quality_count": int(len(radial_velocity)),
        "radial_velocity_median_km_per_s": rv_median,
        "radial_velocity_robust_sigma_km_per_s": robust_sigma(radial_velocity),
        "literature_radial_velocity_km_per_s": LITERATURE_RV_KMS,
        "literature_radial_velocity_error_km_per_s": LITERATURE_RV_ERROR_KMS,
        "notes": [
            "Inverse-parallax distance is descriptive, not a Bayesian distance estimate.",
            "Gaia DR3 parallax zero-point corrections were not applied.",
            "The radial-velocity summary can be broadened by binaries and contaminants.",
        ],
    }
