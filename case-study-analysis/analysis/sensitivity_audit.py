"""Fixed revival checks against the retained snapshot; never alters source data.

Run from the continuation root with:
  PYTHONPATH=analysis/reproduction/src analysis/reproduction/.venv/bin/python \
    analysis/sensitivity_audit.py

The experiment list is prescribed in research/PROTOCOL.md. These are descriptive
set comparisons, not classification accuracy or calibrated membership estimates.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import HDBSCAN
from sklearn.preprocessing import RobustScaler

from gaia_pleiades.clustering import fit_clusters, jaccard_index
from gaia_pleiades.config import (
    FEATURE_COLUMNS,
    FIELD_CENTER_DEC_DEG,
    FIELD_CENTER_RA_DEG,
    FIELD_RADIUS_DEG,
    MIN_CLUSTER_SIZE,
    MIN_SAMPLES,
    SCALER_QUANTILE_RANGE,
    STRENGTH_THRESHOLD,
    TARGET_ANCHOR,
    TARGET_ANCHOR_SCALES,
    ProjectPaths,
)
from gaia_pleiades.data import load_gaia, load_reference_members, verify_manifest


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "checks"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(OUT / name, index=False, float_format="%.17g", lineterminator="\n")


def finite_summary(values: pd.Series) -> dict:
    array = values.to_numpy(dtype=float)
    finite = array[np.isfinite(array)]
    result = {"total_rows": len(array), "finite_rows": len(finite)}
    if len(finite):
        result.update(
            zip(
                ("min", "p05", "p25", "median", "p75", "p95", "max"),
                map(float, np.quantile(finite, (0, 0.05, 0.25, 0.5, 0.75, 0.95, 1))),
            )
        )
    return result


def alternative_fit(frame: pd.DataFrame, columns: tuple[str, ...], min_samples: int):
    """Keep original model defaults; restrict anchor distance to fitted columns."""
    features = frame.loc[:, columns].to_numpy(dtype=float)
    assert np.isfinite(features).all()
    scaled = RobustScaler(quantile_range=SCALER_QUANTILE_RANGE).fit_transform(features)
    model = HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=min_samples,
        cluster_selection_method="eom",
        allow_single_cluster=False,
        copy=True,
    )
    labels = model.fit_predict(scaled)
    rows = []
    indices = [FEATURE_COLUMNS.index(column) for column in columns]
    anchor = np.asarray(TARGET_ANCHOR)[indices]
    scales = np.asarray(TARGET_ANCHOR_SCALES)[indices]
    for label in sorted(set(labels) - {-1}):
        group = frame.loc[labels == label]
        medians = group.loc[:, columns].median().to_numpy()
        rows.append(
            {
                "cluster_label": int(label),
                "count": len(group),
                "parallax_median": float(group["parallax"].median()),
                "pmra_median": float(group["pmra"].median()),
                "pmdec_median": float(group["pmdec"].median()),
                "anchor_distance": float(np.linalg.norm((medians - anchor) / scales)),
            }
        )
    summaries = pd.DataFrame(rows)
    if summaries.empty:
        raise RuntimeError(f"No non-noise component for {columns}, {min_samples}")
    target = int(summaries.loc[summaries["anchor_distance"].idxmin(), "cluster_label"])
    summaries["is_selected_component"] = summaries["cluster_label"].eq(target)
    return labels, np.asarray(model.probabilities_), target, summaries


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = ProjectPaths(ROOT / "analysis" / "reproduction")
    manifest = verify_manifest(paths)
    frame = load_gaia(paths)
    members = load_reference_members(paths)
    assert frame["source_id"].str.fullmatch(r"\d+").all()
    assert not frame["source_id"].duplicated().any()
    assert not members["source_id"].duplicated().any()
    assert np.isfinite(frame.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float)).all()
    field_ids = set(frame["source_id"])
    reference = members.loc[
        members["catalog_probability"].ge(0.5) & members["inrt"].eq(1)
    ]
    reference_ids = set(reference["source_id"])
    eligible = reference_ids & field_ids
    csv(
        reference.loc[~reference["source_id"].isin(field_ids)],
        "reference_absent_from_snapshot.csv",
    )

    # Great-circle distance on the unit sphere, independent of the archive query.
    ra, dec = np.deg2rad(frame["ra"]), np.deg2rad(frame["dec"])
    ra0, dec0 = np.deg2rad([FIELD_CENTER_RA_DEG, FIELD_CENTER_DEC_DEG])
    haversine = (
        np.sin((dec - dec0) / 2) ** 2
        + np.cos(dec) * np.cos(dec0) * np.sin((ra - ra0) / 2) ** 2
    )
    separation = np.rad2deg(2 * np.arcsin(np.sqrt(np.clip(haversine, 0, 1))))
    cuts = {
        "spherical_separation_deg <= 5": separation.le(FIELD_RADIUS_DEG),
        "2 <= parallax <= 15": frame["parallax"].between(2, 15),
        "-20 <= pmra <= 50": frame["pmra"].between(-20, 50),
        "-80 <= pmdec <= -10": frame["pmdec"].between(-80, -10),
        "parallax_over_error > 10": frame["parallax_over_error"].gt(10),
        "pmra_error < 1": frame["pmra_error"].lt(1),
        "pmdec_error < 1": frame["pmdec_error"].lt(1),
        "ruwe < 1.4": frame["ruwe"].lt(1.4),
        "visibility_periods_used > 8": frame["visibility_periods_used"].gt(8),
        "phot_g_mean_mag < 20": frame["phot_g_mean_mag"].lt(20),
        "bp_rp IS NOT NULL": frame["bp_rp"].notna(),
        "phot_bp_mean_flux_over_error > 10": frame["phot_bp_mean_flux_over_error"].gt(
            10
        ),
        "phot_rp_mean_flux_over_error > 10": frame["phot_rp_mean_flux_over_error"].gt(
            10
        ),
    }
    cut_table = pd.DataFrame(
        {
            "cut": name,
            "rows_checked": len(frame),
            "passing_rows": int(mask.fillna(False).sum()),
            "failing_rows": int((~mask.fillna(False)).sum()),
        }
        for name, mask in cuts.items()
    )
    csv(cut_table, "query_cut_audit.csv")
    assert cut_table["failing_rows"].eq(0).all(), (
        "Retained row violates committed query"
    )

    original = fit_clusters(frame)
    labels, strengths, target = (
        original.labels,
        original.strengths,
        original.target_label,
    )
    main_mask = (labels == target) & (strengths >= STRENGTH_THRESHOLD)
    main_ids = set(frame.loc[main_mask, "source_id"])
    rectangle = np.all(
        np.abs(frame.loc[:, FEATURE_COLUMNS].to_numpy() - np.asarray(TARGET_ANCHOR))
        <= np.array([1.0, 5.0, 10.0]),
        axis=1,
    )
    rectangle_ids = set(frame.loc[rectangle, "source_id"])

    rows, id_rows, components = [], [], []

    def record(
        name,
        family,
        mask,
        *,
        threshold=None,
        fit_labels=None,
        fit_target=None,
        features=None,
        samples=None,
    ):
        selected = frame.loc[mask]
        ids = set(selected["source_id"])
        overlap = ids & reference_ids
        row = {
            "experiment": name,
            "family": family,
            "features": features,
            "min_samples": samples,
            "strength_threshold": threshold,
            "candidate_count": len(ids),
            "target_component_count": int((fit_labels == fit_target).sum())
            if fit_labels is not None
            else None,
            "noise_count": int((fit_labels == -1).sum())
            if fit_labels is not None
            else None,
            "shared_with_main": len(ids & main_ids),
            "added_vs_main": len(ids - main_ids),
            "lost_vs_main": len(main_ids - ids),
            "jaccard_vs_main": jaccard_index(ids, main_ids),
            "shared_with_rectangle": len(ids & rectangle_ids),
            "jaccard_vs_rectangle": jaccard_index(ids, rectangle_ids),
            "reference_members_total": len(reference_ids),
            "reference_members_in_snapshot": len(eligible),
            "reference_intersection": len(overlap),
            "selected_only_vs_reference": len(ids - reference_ids),
            "eligible_reference_not_selected": len(eligible - ids),
            "jaccard_vs_eligible_reference": jaccard_index(ids, eligible),
            "parallax_median_mas": float(selected["parallax"].median()),
            "pmra_median_mas_per_yr": float(selected["pmra"].median()),
            "pmdec_median_mas_per_yr": float(selected["pmdec"].median()),
        }
        rows.append(row)
        id_rows.extend(
            {"experiment": name, "source_id": source_id} for source_id in sorted(ids)
        )

    record(
        "main",
        "main",
        main_mask,
        threshold=0.5,
        fit_labels=labels,
        fit_target=target,
        features="parallax,pmra,pmdec",
        samples=MIN_SAMPLES,
    )
    for threshold in (0.3, 0.5, 0.7, 0.9):
        record(
            f"threshold_{threshold:.1f}",
            "strength_threshold",
            (labels == target) & (strengths >= threshold),
            threshold=threshold,
            fit_labels=labels,
            fit_target=target,
            features="parallax,pmra,pmdec",
            samples=MIN_SAMPLES,
        )
    for samples in (5, 10, 20):
        alt_labels, alt_strengths, alt_target, summaries = alternative_fit(
            frame, FEATURE_COLUMNS, samples
        )
        name = f"min_samples_{samples}"
        summaries.insert(0, "experiment", name)
        components.append(summaries)
        alt_mask = (alt_labels == alt_target) & (alt_strengths >= 0.5)
        if samples == MIN_SAMPLES:
            assert np.array_equal(alt_labels, labels)
            assert np.array_equal(alt_strengths, strengths)
            assert alt_target == target
        record(
            name,
            "min_samples",
            alt_mask,
            threshold=0.5,
            fit_labels=alt_labels,
            fit_target=alt_target,
            features="parallax,pmra,pmdec",
            samples=samples,
        )
    pm_labels, pm_strengths, pm_target, summaries = alternative_fit(
        frame, ("pmra", "pmdec"), MIN_SAMPLES
    )
    summaries.insert(0, "experiment", "proper_motion_only")
    components.append(summaries)
    record(
        "proper_motion_only",
        "feature_ablation",
        (pm_labels == pm_target) & (pm_strengths >= 0.5),
        threshold=0.5,
        fit_labels=pm_labels,
        fit_target=pm_target,
        features="pmra,pmdec",
        samples=MIN_SAMPLES,
    )
    record(
        "fixed_rectangle", "simple_baseline", rectangle, features="parallax,pmra,pmdec"
    )
    table = pd.DataFrame(rows)
    csv(table, "sensitivity_summary.csv")
    csv(
        table.loc[table["family"].eq("strength_threshold")], "threshold_sensitivity.csv"
    )
    csv(pd.DataFrame(id_rows), "sensitivity_candidate_ids.csv")
    csv(pd.concat(components, ignore_index=True), "alternative_component_summaries.csv")

    subsets = {"retained_field": frame, "main_candidates": frame.loc[main_mask]}
    csv(
        pd.DataFrame(
            {
                "subset": name,
                "column": column,
                "rows": len(subset),
                "missing_rows": int(subset[column].isna().sum()),
            }
            for name, subset in subsets.items()
            for column in frame.columns
        ),
        "missingness.csv",
    )
    distributions = (
        "parallax_error",
        "pmra_error",
        "pmdec_error",
        "parallax_over_error",
        "ruwe",
        "phot_g_mean_mag",
        "radial_velocity_error",
        "parallax_pmra_corr",
        "parallax_pmdec_corr",
        "pmra_pmdec_corr",
    )
    csv(
        pd.DataFrame(
            {"subset": name, "column": column, **finite_summary(subset[column])}
            for name, subset in subsets.items()
            for column in distributions
        ),
        "measurement_distributions.csv",
    )
    rv_rows = []
    for name, subset in subsets.items():
        rv = subset["radial_velocity"].notna()
        usable = (
            rv
            & subset["radial_velocity_error"].notna()
            & subset["radial_velocity_error"].lt(5)
        )
        rv_rows.append(
            {
                "subset": name,
                "rows": len(subset),
                "rv_present": int(rv.sum()),
                "rv_missing": int((~rv).sum()),
                "rv_error_lt5": int(usable.sum()),
                "quality_rv_median_km_s": float(
                    subset.loc[usable, "radial_velocity"].median()
                ),
                "quality_rv_robust_sigma_km_s": float(
                    1.4826
                    * (
                        subset.loc[usable, "radial_velocity"]
                        - subset.loc[usable, "radial_velocity"].median()
                    )
                    .abs()
                    .median()
                ),
                "quality_rv_g_median": float(
                    subset.loc[usable, "phot_g_mean_mag"].median()
                ),
                "remaining_rows_g_median": float(
                    subset.loc[~usable, "phot_g_mean_mag"].median()
                ),
            }
        )
    csv(pd.DataFrame(rv_rows), "radial_velocity_availability.csv")

    # Deliberate teaching examples chosen by a disclosed deterministic rule.
    examples = frame.copy()
    examples["cluster_label"] = labels
    examples["cluster_strength"] = strengths
    examples["is_target_component"] = labels == target
    examples["is_main_candidate"] = main_mask
    examples["in_filtered_reference"] = examples["source_id"].isin(reference_ids)
    examples["in_fixed_rectangle"] = rectangle
    examples["spherical_separation_deg"] = separation
    examples["anchor_distance"] = np.linalg.norm(
        (frame.loc[:, FEATURE_COLUMNS].to_numpy() - np.asarray(TARGET_ANCHOR))
        / np.asarray(TARGET_ANCHOR_SCALES),
        axis=1,
    )
    rules = [
        (
            "strong_candidate",
            examples.loc[main_mask]
            .sort_values(
                ["cluster_strength", "anchor_distance", "source_id"],
                ascending=[False, True, True],
            )
            .iloc[0],
            "Highest assignment strength, then nearest 3D anchor, then source ID; illustrative, not representative.",
        ),
        (
            "just_above_threshold",
            examples.loc[main_mask]
            .sort_values(["cluster_strength", "source_id"])
            .iloc[0],
            "Lowest retained assignment strength at or above 0.5, then source ID.",
        ),
        (
            "just_below_threshold",
            examples.loc[(labels == target) & ~main_mask]
            .sort_values(["cluster_strength", "source_id"], ascending=[False, True])
            .iloc[0],
            "Highest target-component strength below 0.5, then source ID; excluded by convention, not proven nonmember.",
        ),
        (
            "outside_target_component",
            examples.loc[labels != target]
            .sort_values(["anchor_distance", "source_id"])
            .iloc[0],
            "Nearest 3D anchor among sources outside selected component; this algorithmic exclusion does not establish nonmembership.",
        ),
        (
            "candidate_absent_from_filtered_reference",
            examples.loc[main_mask & ~examples["in_filtered_reference"]]
            .sort_values(["cluster_strength", "source_id"], ascending=[False, True])
            .iloc[0],
            "Highest-strength candidate absent from filtered comparison catalog, then source ID; absence is not proof of a false positive.",
        ),
    ]
    example_rows = []
    for role, row, rule in rules:
        record_row = row.to_dict()
        record_row.update({"teaching_role": role, "selection_rule": rule})
        example_rows.append(record_row)
    example_table = pd.DataFrame(example_rows)
    csv(example_table, "teaching_examples.csv")
    # JSON preserves numeric-looking source IDs as JSON strings for web consumers.
    (OUT / "teaching_examples.json").write_text(
        example_table.to_json(orient="records", indent=2) + "\n"
    )

    correlation_columns = (
        "parallax_pmra_corr",
        "parallax_pmdec_corr",
        "pmra_pmdec_corr",
    )
    audit = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "pandas", "scikit-learn")
        },
        "script_sha256": sha256(Path(__file__)),
        "protocol_sha256": sha256(ROOT / "research" / "PROTOCOL.md"),
        "inputs": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (
                paths.raw_gaia,
                paths.reference_members,
                paths.query,
                paths.root / "uv.lock",
                paths.root / "src" / "gaia_pleiades" / "clustering.py",
                paths.root / "src" / "gaia_pleiades" / "config.py",
                paths.root / "src" / "gaia_pleiades" / "data.py",
            )
        },
        "snapshot_acquired_at_utc": manifest["acquired_at_utc"],
        "retained_rows": len(frame),
        "unique_source_ids": len(field_ids),
        "reference_rows": len(members),
        "filtered_reference_ids": len(reference_ids),
        "reference_in_snapshot": len(eligible),
        "reference_absent_from_snapshot": len(reference_ids - field_ids),
        "spherical_separation_deg": finite_summary(separation),
        "clustering_feature_nonfinite_values": int(
            (~np.isfinite(frame.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float))).sum()
        ),
        "all_committed_query_cuts_pass": bool(cut_table["failing_rows"].eq(0).all()),
        "correlation_terms_present": list(correlation_columns),
        "correlation_terms_missing_rows": {
            col: int(frame[col].isna().sum()) for col in correlation_columns
        },
        "main_candidate_count": len(main_ids),
        "identical_independent_min_samples_10_reimplementation": True,
        "rectangle_center": list(TARGET_ANCHOR),
        "rectangle_half_widths": [1, 5, 10],
        "caveats": [
            "The input is an already filtered snapshot, not the complete field; this audit verifies retained rows only.",
            "Absent filtered-reference IDs cannot be assigned cut-failure reasons from these files.",
            "Catalog overlap is not accuracy: both analyses use Gaia DR3 and density clustering.",
            "Assignment strength is not a calibrated astrophysical membership probability.",
            "The three pairwise astrometric correlation columns are present; no error propagation was undertaken in this fixed sensitivity scope.",
            "The PM-only ablation still uses the parallax-prefiltered snapshot and changes only clustering inputs.",
            "Alternative assignment-strength thresholds are model-specific conventions; comparisons do not rank scientific correctness.",
            "The simple rectangle uses the external anchor, including pmDec=-50, not an outcome-tuned center.",
            "RV is held out from clustering, but only a bright subset has usable values; CMD is partly coupled through parallax and photometric preselection.",
        ],
    }
    (OUT / "audit.json").write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n")
    output_hashes = {
        path.name: sha256(path)
        for path in sorted(OUT.iterdir())
        if path.suffix in {".csv", ".json"} and path.name != "output_hashes.json"
    }
    (OUT / "output_hashes.json").write_text(json.dumps(output_hashes, indent=2) + "\n")
    print(
        table[
            [
                "experiment",
                "candidate_count",
                "shared_with_main",
                "added_vs_main",
                "lost_vs_main",
                "jaccard_vs_main",
                "reference_intersection",
            ]
        ].to_string(index=False)
    )
    print(
        json.dumps(
            {
                "query_cuts_pass": audit["all_committed_query_cuts_pass"],
                "rows": len(frame),
                "reference_absent": len(reference_ids - field_ids),
                "max_radius_deg": float(separation.max()),
                "output_directory": str(OUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
