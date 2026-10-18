"""End-to-end orchestration and offline verification."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from gaia_pleiades.clustering import (
    add_assignments,
    fit_clusters,
    model_bundle,
    run_sensitivity,
)
from gaia_pleiades.config import (
    FEATURE_COLUMNS,
    MIN_CLUSTER_SIZE,
    MIN_SAMPLES,
    SCALER_QUANTILE_RANGE,
    STRENGTH_THRESHOLD,
    ProjectPaths,
)
from gaia_pleiades.data import (
    acquire_datasets,
    load_gaia,
    load_reference_cluster,
    load_reference_members,
    sha256_file,
    verify_manifest,
)
from gaia_pleiades.photometry import add_derived_columns
from gaia_pleiades.reporting import generate_report_artifacts
from gaia_pleiades.validation import candidate_statistics, reference_agreement

CANDIDATE_COLUMNS = [
    "source_id",
    "ra",
    "dec",
    "l",
    "b",
    "parallax",
    "parallax_error",
    "pmra",
    "pmra_error",
    "pmdec",
    "pmdec_error",
    "ruwe",
    "visibility_periods_used",
    "phot_g_mean_mag",
    "phot_bp_mean_mag",
    "phot_rp_mean_mag",
    "bp_rp",
    "absolute_g_naive",
    "distance_pc_inverse_parallax",
    "corrected_bp_rp_excess",
    "radial_velocity",
    "radial_velocity_error",
    "cluster_label",
    "cluster_strength",
    "is_in_reference_catalog",
]


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, float_format="%.12g", lineterminator="\n")


def _stability_metrics(sensitivity: pd.DataFrame) -> dict[str, Any]:
    cluster_size = sensitivity.loc[sensitivity["experiment"].eq("cluster_size")]
    iqr = sensitivity.loc[sensitivity["experiment"].eq("scaler_iqr")].iloc[0]
    return {
        "min_cluster_sizes_tested": cluster_size["min_cluster_size"].astype(int).tolist(),
        "candidate_count_min": int(cluster_size["candidate_count"].min()),
        "candidate_count_max": int(cluster_size["candidate_count"].max()),
        "jaccard_min": float(cluster_size["jaccard_vs_main"].min()),
        "jaccard_max": float(cluster_size["jaccard_vs_main"].max()),
        "iqr_scaler_candidate_count": int(iqr["candidate_count"]),
        "iqr_scaler_jaccard": float(iqr["jaccard_vs_main"]),
    }


def _write_artifact_manifest(paths: ProjectPaths) -> None:
    files = [paths.processed_field, paths.candidates]
    files.extend(
        path
        for path in sorted(paths.outputs.rglob("*"))
        if path.is_file() and path != paths.artifact_manifest
    )
    manifest = {
        "schema_version": 1,
        "files": {str(path.relative_to(paths.root)): sha256_file(path) for path in sorted(files)},
    }
    paths.artifact_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _resolve_manifest_artifact(root: Path, relative: str) -> Path:
    """Resolve one manifest entry to a contained, non-symlink regular file."""
    resolved_root = root.resolve(strict=True)
    manifest_path = Path(relative)
    if manifest_path.is_absolute():
        raise ValueError("absolute paths are not allowed")
    if ".." in manifest_path.parts:
        raise ValueError("parent traversal is not allowed")

    candidate = resolved_root
    for part in manifest_path.parts:
        candidate = candidate / part
        try:
            mode = candidate.lstat().st_mode
        except FileNotFoundError as error:
            raise FileNotFoundError(relative) from error
        except NotADirectoryError as error:
            raise ValueError("a path component is not a directory") from error
        if stat.S_ISLNK(mode):
            raise ValueError("symlinks are not allowed")

    resolved_candidate = candidate.resolve(strict=True)
    if not resolved_candidate.is_relative_to(resolved_root):
        raise ValueError("path escapes the artifact root")
    if not stat.S_ISREG(resolved_candidate.stat().st_mode):
        raise ValueError("target is not a regular file")
    return resolved_candidate


def run_pipeline(root: Path, refresh_data: bool = False) -> dict[str, Any]:
    """Acquire data, fit the model, validate the result, and render outputs."""
    paths = ProjectPaths(root.resolve())
    paths.make_directories()
    dataset_manifest = acquire_datasets(paths, refresh=refresh_data)

    field = add_derived_columns(load_gaia(paths))
    if field["source_id"].duplicated().any():
        raise RuntimeError("The Gaia field contains duplicate source_id values")

    clustering = fit_clusters(field)
    field = add_assignments(field, clustering)

    reference_members = load_reference_members(paths)
    reference_cluster = load_reference_cluster(paths)
    high_confidence_reference_ids = set(
        reference_members.loc[
            reference_members["catalog_probability"].ge(0.5) & reference_members["inrt"].eq(1),
            "source_id",
        ].astype(str)
    )
    field["is_in_reference_catalog"] = (
        field["source_id"].astype(str).isin(high_confidence_reference_ids)
    )
    candidates = field.loc[field["is_candidate"]].copy()
    candidates = candidates.sort_values("source_id", kind="stable").reset_index(drop=True)

    candidate_ids = set(candidates["source_id"].astype(str))
    sensitivity = run_sensitivity(field, candidate_ids)
    agreement = reference_agreement(field, candidates, reference_members)
    statistics = candidate_statistics(candidates, reference_cluster)

    cluster_summaries = clustering.summaries.copy()
    cluster_summaries["is_selected_target"] = cluster_summaries["cluster_label"].eq(
        clustering.target_label
    )
    metrics = {
        "schema_version": 1,
        "result_label": "Pleiades kinematic candidate members",
        "sample": {
            "quality_filtered_sources": int(len(field)),
            "target_component_sources": int(field["is_target_cluster"].sum()),
            "noise_sources": int(field["cluster_label"].eq(-1).sum()),
            "candidate_sources": int(len(candidates)),
        },
        "method": {
            "features": list(FEATURE_COLUMNS),
            "scaler": "RobustScaler",
            "quantile_range": list(SCALER_QUANTILE_RANGE),
            "clusterer": "sklearn.cluster.HDBSCAN",
            "min_cluster_size": MIN_CLUSTER_SIZE,
            "min_samples": MIN_SAMPLES,
            "candidate_strength_threshold": STRENGTH_THRESHOLD,
            "target_cluster_label": clustering.target_label,
            "warning": "Assignment strength is not a calibrated membership probability.",
        },
        "candidate_statistics": statistics,
        "reference_agreement": agreement,
        "stability": _stability_metrics(sensitivity),
        "data_provenance": {
            "gaia_sha256": dataset_manifest["gaia"]["sha256"],
            "reference_members_sha256": dataset_manifest["reference"]["member_sha256"],
            "reference_cluster_sha256": dataset_manifest["reference"]["cluster_sha256"],
        },
    }

    field = field.sort_values("source_id", kind="stable").reset_index(drop=True)
    _write_csv(field, paths.processed_field)
    _write_csv(candidates.loc[:, CANDIDATE_COLUMNS], paths.candidates)
    _write_csv(cluster_summaries, paths.tables / "cluster_summaries.csv")
    _write_csv(sensitivity, paths.tables / "parameter_sensitivity.csv")
    _write_csv(pd.DataFrame([agreement]), paths.tables / "catalog_agreement.csv")
    joblib.dump(model_bundle(clustering), paths.model, compress=3)
    generate_report_artifacts(paths, field, candidates, reference_cluster, sensitivity, metrics)
    _write_artifact_manifest(paths)
    return metrics


def verify_artifacts(root: Path) -> dict[str, Any]:
    """Verify file integrity and independently recompute the cached candidate IDs."""
    paths = ProjectPaths(root.resolve())
    verify_manifest(paths)

    artifact_manifest = json.loads(paths.artifact_manifest.read_text(encoding="utf-8"))
    integrity_failures = []
    for relative, expected_digest in artifact_manifest["files"].items():
        try:
            path = _resolve_manifest_artifact(paths.root, relative)
        except FileNotFoundError:
            integrity_failures.append(f"{relative}: missing")
            continue
        except ValueError as error:
            integrity_failures.append(f"{relative}: Unsafe artifact manifest path ({error})")
            continue
        actual_digest = sha256_file(path)
        if actual_digest != expected_digest:
            integrity_failures.append(
                f"{relative}: expected {expected_digest}, got {actual_digest}"
            )
    if integrity_failures:
        raise RuntimeError("Artifact integrity check failed:\n" + "\n".join(integrity_failures))

    raw = add_derived_columns(load_gaia(paths))
    recomputed = add_assignments(raw, fit_clusters(raw))
    recomputed_candidates = recomputed.loc[recomputed["is_candidate"]].sort_values("source_id")
    cached_candidates = pd.read_csv(paths.candidates, dtype={"source_id": "string"}).sort_values(
        "source_id"
    )
    if cached_candidates["source_id"].duplicated().any():
        raise RuntimeError("Cached candidates contain duplicate source_id values")
    if not np.array_equal(
        recomputed_candidates["source_id"].astype(str).to_numpy(),
        cached_candidates["source_id"].astype(str).to_numpy(),
    ):
        raise RuntimeError("Cached candidate IDs do not match an independent clustering rerun")
    if not np.allclose(
        recomputed_candidates["cluster_strength"].to_numpy(),
        cached_candidates["cluster_strength"].to_numpy(),
        rtol=1e-9,
        atol=1e-10,
    ):
        raise RuntimeError("Cached assignment strengths do not match an independent rerun")

    metrics = json.loads(paths.metrics.read_text(encoding="utf-8"))
    if metrics["sample"]["candidate_sources"] != len(cached_candidates):
        raise RuntimeError("Candidate count disagrees with metrics.json")
    for figure in paths.figures.glob("*.png"):
        if figure.stat().st_size < 10_000 or figure.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"Figure is missing, truncated, or not PNG: {figure}")

    return {
        "quality_filtered_sources": int(len(raw)),
        "candidate_sources": int(len(cached_candidates)),
        "verified_artifacts": int(len(artifact_manifest["files"])),
        "status": "verified",
    }
