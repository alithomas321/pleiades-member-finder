"""Data acquisition, normalization, and provenance tracking."""

from __future__ import annotations

import hashlib
import io
import json
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.exceptions import HTTPError

from gaia_pleiades.config import (
    REFERENCE_CATALOG,
    REFERENCE_CLUSTER_NAME,
    ProjectPaths,
)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.12g", lineterminator="\n")


def _source_ids_as_strings(values: pd.Series) -> pd.Series:
    """Normalize Gaia identifiers without allowing floating-point conversion."""
    return values.astype("string").str.replace(r"\.0$", "", regex=True)


def download_gaia(paths: ProjectPaths) -> dict[str, Any]:
    """Run the committed Gaia TAP query asynchronously, with a bounded sync fallback."""
    from astroquery.gaia import Gaia

    query = paths.query.read_text(encoding="utf-8")
    Gaia.ROW_LIMIT = -1
    access_mode = "asynchronous"
    job_id = "unknown"
    try:
        job = Gaia.launch_job_async(query, dump_to_file=False)
        frame = job.get_results().to_pandas()
        job_id = str(getattr(job, "jobid", "unknown"))
    except HTTPError as error:
        warnings.warn(
            f"Gaia asynchronous result retrieval failed ({error}); using TAP sync fallback.",
            RuntimeWarning,
            stacklevel=2,
        )
        response = requests.post(
            "https://gea.esac.esa.int/tap-server/tap/sync",
            data={
                "REQUEST": "doQuery",
                "LANG": "ADQL",
                "FORMAT": "csv",
                "MAXREC": "20000",
                "QUERY": query,
            },
            timeout=(30, 300),
        )
        response.raise_for_status()
        if not response.text.startswith("source_id,"):
            raise RuntimeError(
                f"Gaia sync fallback did not return CSV: {response.text[:500]}"
            ) from error
        frame = pd.read_csv(io.StringIO(response.text), dtype={"source_id": "string"})
        if len(frame) >= 20_000:
            raise RuntimeError(
                "Gaia sync fallback reached MAXREC; query result may be truncated"
            ) from error
        access_mode = "synchronous fallback after asynchronous HTTP 500"
    frame.columns = [str(column) for column in frame.columns]
    frame["source_id"] = _source_ids_as_strings(frame["source_id"])
    frame = frame.sort_values("source_id", kind="stable").reset_index(drop=True)
    _write_csv(frame, paths.raw_gaia)
    return {
        "service": "Gaia Archive TAP",
        "table": "gaiadr3.gaia_source",
        "job_id": job_id,
        "access_mode": access_mode,
        "rows": int(len(frame)),
        "query_path": str(paths.query.relative_to(paths.root)),
        "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "file": str(paths.raw_gaia.relative_to(paths.root)),
        "sha256": sha256_file(paths.raw_gaia),
    }


def _decode_text_columns(frame: pd.DataFrame) -> pd.DataFrame:
    for column in frame.select_dtypes(include=["object"]).columns:
        frame[column] = frame[column].map(
            lambda value: value.decode("utf-8") if isinstance(value, bytes) else value
        )
    return frame


def _vizier_query(table: str) -> pd.DataFrame:
    from astroquery.vizier import Vizier

    # VizieR's "*" means default columns; "**" is required for non-default
    # validation fields such as tidal radius and minClSize.
    client = Vizier(columns=["**"], row_limit=-1)
    result = client.query_constraints(
        catalog=f"{REFERENCE_CATALOG}/{table}",
        Name=REFERENCE_CLUSTER_NAME,
        cache=False,
    )
    if len(result) != 1:
        raise RuntimeError(f"Expected one VizieR table for {table}, received {len(result)}")
    frame = result[0].to_pandas()
    frame.columns = [str(column) for column in frame.columns]
    return _decode_text_columns(frame)


def download_reference_catalog(paths: ProjectPaths) -> dict[str, Any]:
    """Cache the current Hunt & Reffert (2024) Pleiades validation rows."""
    members = _vizier_query("members")
    cluster = _vizier_query("clusters")

    required_member_columns = {"Name", "GaiaDR3", "inrt", "Prob"}
    required_cluster_columns = {
        "Name",
        "N",
        "Nt",
        "RA_ICRS",
        "DE_ICRS",
        "pmRA",
        "pmDE",
        "Plx",
        "rt",
        "rtot",
        "minClSize",
    }
    if missing := required_member_columns.difference(members.columns):
        raise RuntimeError(f"Missing current reference member columns: {sorted(missing)}")
    if missing := required_cluster_columns.difference(cluster.columns):
        raise RuntimeError(f"Missing current reference cluster columns: {sorted(missing)}")

    members = members.loc[:, sorted(required_member_columns)].rename(
        columns={"GaiaDR3": "source_id", "Prob": "catalog_probability"}
    )
    members["source_id"] = _source_ids_as_strings(members["source_id"])
    members["catalog_probability"] = pd.to_numeric(members["catalog_probability"], errors="raise")
    members["inrt"] = pd.to_numeric(members["inrt"], errors="raise").astype(int)
    members = members.sort_values("source_id", kind="stable").reset_index(drop=True)

    cluster = cluster.loc[:, sorted(required_cluster_columns)].reset_index(drop=True)
    if len(cluster) != 1:
        raise RuntimeError(f"Expected one {REFERENCE_CLUSTER_NAME} cluster row, got {len(cluster)}")

    _write_csv(members, paths.reference_members)
    _write_csv(cluster, paths.reference_cluster)
    return {
        "service": "CDS VizieR",
        "catalog": REFERENCE_CATALOG,
        "cluster_name": REFERENCE_CLUSTER_NAME,
        "member_rows": int(len(members)),
        "member_file": str(paths.reference_members.relative_to(paths.root)),
        "member_sha256": sha256_file(paths.reference_members),
        "cluster_file": str(paths.reference_cluster.relative_to(paths.root)),
        "cluster_sha256": sha256_file(paths.reference_cluster),
        "catalog_doi": "10.26093/cds/vizier.36860042",
        "paper_doi": "10.1051/0004-6361/202348662",
    }


def _existing_gaia_metadata(paths: ProjectPaths) -> dict[str, Any]:
    query = paths.query.read_text(encoding="utf-8")
    rows = len(pd.read_csv(paths.raw_gaia, usecols=["source_id"]))
    return {
        "service": "Gaia Archive TAP",
        "table": "gaiadr3.gaia_source",
        "job_id": "unknown",
        "access_mode": "cached snapshot recovered after partial acquisition",
        "rows": rows,
        "query_path": str(paths.query.relative_to(paths.root)),
        "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "file": str(paths.raw_gaia.relative_to(paths.root)),
        "sha256": sha256_file(paths.raw_gaia),
    }


def _existing_reference_metadata(paths: ProjectPaths) -> dict[str, Any]:
    rows = len(pd.read_csv(paths.reference_members, usecols=["source_id"]))
    return {
        "service": "CDS VizieR",
        "catalog": REFERENCE_CATALOG,
        "cluster_name": REFERENCE_CLUSTER_NAME,
        "member_rows": rows,
        "member_file": str(paths.reference_members.relative_to(paths.root)),
        "member_sha256": sha256_file(paths.reference_members),
        "cluster_file": str(paths.reference_cluster.relative_to(paths.root)),
        "cluster_sha256": sha256_file(paths.reference_cluster),
        "catalog_doi": "10.26093/cds/vizier.36860042",
        "paper_doi": "10.1051/0004-6361/202348662",
    }


def acquire_datasets(paths: ProjectPaths, refresh: bool = False) -> dict[str, Any]:
    """Download missing data, or reuse versioned snapshots with verified hashes."""
    paths.make_directories()
    have_all = all(
        path.exists()
        for path in (
            paths.raw_gaia,
            paths.reference_members,
            paths.reference_cluster,
            paths.manifest,
        )
    )
    if have_all and not refresh:
        return verify_manifest(paths)

    reference_metadata = (
        download_reference_catalog(paths)
        if refresh or not paths.reference_members.exists() or not paths.reference_cluster.exists()
        else _existing_reference_metadata(paths)
    )
    # Download the small reference tables first so a later Gaia archive failure
    # cannot strand a new Gaia snapshot without its complete provenance record.
    gaia_metadata = (
        download_gaia(paths)
        if refresh or not paths.raw_gaia.exists()
        else _existing_gaia_metadata(paths)
    )
    manifest = {
        "acquired_at_utc": datetime.now(UTC).isoformat(),
        "gaia": gaia_metadata,
        "reference": reference_metadata,
        "notes": [
            "The Gaia snapshot is sorted by source_id after TAP retrieval.",
            "The reference catalog is used only for post-clustering validation.",
        ],
    }
    paths.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_manifest(paths: ProjectPaths) -> dict[str, Any]:
    """Verify cached source files against their acquisition manifest."""
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    expected = {
        paths.raw_gaia: manifest["gaia"]["sha256"],
        paths.reference_members: manifest["reference"]["member_sha256"],
        paths.reference_cluster: manifest["reference"]["cluster_sha256"],
    }
    failures = []
    current_query_digest = hashlib.sha256(paths.query.read_bytes()).hexdigest()
    if current_query_digest != manifest["gaia"]["query_sha256"]:
        failures.append(
            f"{paths.query}: expected query hash {manifest['gaia']['query_sha256']}, "
            f"got {current_query_digest}"
        )
    for path, expected_digest in expected.items():
        if not path.exists():
            failures.append(f"{path}: file is missing")
            continue
        actual_digest = sha256_file(path)
        if actual_digest != expected_digest:
            failures.append(f"{path}: expected {expected_digest}, got {actual_digest}")
    if failures:
        raise RuntimeError("Dataset integrity check failed:\n" + "\n".join(failures))
    return manifest


def load_gaia(paths: ProjectPaths) -> pd.DataFrame:
    frame = pd.read_csv(paths.raw_gaia, dtype={"source_id": "string"})
    return frame.sort_values("source_id", kind="stable").reset_index(drop=True)


def load_reference_members(paths: ProjectPaths) -> pd.DataFrame:
    return pd.read_csv(paths.reference_members, dtype={"source_id": "string"})


def load_reference_cluster(paths: ProjectPaths) -> pd.DataFrame:
    return pd.read_csv(paths.reference_cluster)
